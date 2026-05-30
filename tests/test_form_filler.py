"""Tests for :mod:`form_filler.FormFiller`.

These tests patch every external dependency (driver, fill_field,
load_spreadsheet, export_results) so they exercise the orchestration
logic without touching a real browser or filesystem beyond ``tmp_path``.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from form_filler import FormFiller


@pytest.fixture
def base_config() -> dict:
    """A minimal config that matches the conftest valid_dataframe schema."""
    return {
        "target": {
            "url": "https://demoqa.com/automation-practice-form",
            "submit_selector": "#submit",
            "confirmation_selector": ".modal-content",
        },
        "behavior": {"headless": True},
        "fields": {
            "first_name": {"type": "text", "selector": "#firstName"},
            "last_name": {"type": "text", "selector": "#lastName"},
            "email": {"type": "text", "selector": "#userEmail"},
            "gender": {"type": "radio", "selector": "label[for^='gender-radio']"},
            "mobile": {"type": "text", "selector": "#userNumber"},
            "state": {"type": "dropdown", "selector": "#state"},
        },
    }


@pytest.fixture
def filler(base_config: dict, tmp_path: Path) -> FormFiller:
    """A FormFiller wired to a temporary output directory."""
    return FormFiller(
        config=base_config,
        input_path=tmp_path / "in.xlsx",
        output_dir=tmp_path / "out",
        log_path=tmp_path / "logs" / "run.log",
    )


def test_init_sets_paths_and_config(filler: FormFiller, tmp_path: Path) -> None:
    """__init__ wires every public attribute correctly."""
    assert filler.input_path == tmp_path / "in.xlsx"
    assert filler.output_dir == tmp_path / "out"
    assert filler.screenshots_dir == tmp_path / "out" / "screenshots"
    assert filler.results_path == tmp_path / "out" / "results.xlsx"
    assert "first_name" in filler.field_specs


@patch("form_filler.FormFiller._submit_and_capture")
@patch("form_filler.fill_field")
def test_process_row_success_returns_success_status(
    mock_fill, mock_submit, filler: FormFiller
) -> None:
    """A clean row returns ('success', '')."""
    driver = MagicMock()
    row = {
        "first_name": "Ana", "last_name": "Souza", "email": "a@x.com",
        "gender": "Female", "mobile": "0991234567", "state": "NCR",
    }

    status, error = filler._process_row(driver, 0, row)

    assert status == "success"
    assert error == ""
    # fill_field called once per declared field.
    assert mock_fill.call_count == len(filler.field_specs)


@patch("form_filler.FormFiller._capture_screenshot")
@patch("form_filler.fill_field")
def test_process_row_isolates_failure(
    mock_fill, mock_screenshot, filler: FormFiller
) -> None:
    """A raised exception is captured as ('error', '<message>')."""
    mock_fill.side_effect = RuntimeError("boom")
    driver = MagicMock()
    row = {
        "first_name": "Ana", "last_name": "Souza", "email": "a@x.com",
        "gender": "Female", "mobile": "0991234567", "state": "NCR",
    }

    status, error = filler._process_row(driver, 3, row)

    assert status == "error"
    assert "boom" in error


@patch("form_filler.export_results")
@patch("form_filler.build_driver")
@patch("form_filler.FormFiller._process_row")
@patch("form_filler.load_spreadsheet")
def test_run_appends_status_and_error_columns(
    mock_load, mock_process, mock_build_driver, mock_export,
    filler: FormFiller, valid_dataframe: pd.DataFrame,
) -> None:
    """run() returns the DataFrame augmented with status/error."""
    mock_load.return_value = valid_dataframe
    mock_process.side_effect = [("success", ""), ("error", "timeout")]
    mock_build_driver.return_value = MagicMock()

    result_df = filler.run()

    assert "status" in result_df.columns
    assert "error" in result_df.columns
    assert result_df["status"].tolist() == ["success", "error"]
    assert result_df["error"].tolist() == ["", "timeout"]


@patch("form_filler.export_results")
@patch("form_filler.build_driver")
@patch("form_filler.FormFiller._process_row")
@patch("form_filler.load_spreadsheet")
def test_run_respects_limit(
    mock_load, mock_process, mock_build_driver, mock_export,
    filler: FormFiller, valid_dataframe: pd.DataFrame,
) -> None:
    """limit=N truncates the DataFrame before processing."""
    # Build a longer DataFrame so the limit has something to cut.
    longer = pd.concat([valid_dataframe] * 5, ignore_index=True)  # 10 rows
    mock_load.return_value = longer
    mock_process.return_value = ("success", "")
    mock_build_driver.return_value = MagicMock()

    result_df = filler.run(limit=3)

    assert len(result_df) == 3
    assert mock_process.call_count == 3


@patch("form_filler.export_results")
@patch("form_filler.build_driver")
@patch("form_filler.FormFiller._process_row")
@patch("form_filler.load_spreadsheet")
def test_run_calls_export_results_once(
    mock_load, mock_process, mock_build_driver, mock_export,
    filler: FormFiller, valid_dataframe: pd.DataFrame,
) -> None:
    """run() writes results.xlsx exactly once at the end."""
    mock_load.return_value = valid_dataframe
    mock_process.return_value = ("success", "")
    mock_build_driver.return_value = MagicMock()

    filler.run()

    mock_export.assert_called_once()


@patch("form_filler.export_results")
@patch("form_filler.build_driver")
@patch("form_filler.FormFiller._process_row")
@patch("form_filler.load_spreadsheet")
def test_run_quits_driver_even_on_exception(
    mock_load, mock_process, mock_build_driver, mock_export,
    filler: FormFiller, valid_dataframe: pd.DataFrame,
) -> None:
    """If processing raises mid-run, the driver is still quit cleanly."""
    mock_driver = MagicMock()
    mock_build_driver.return_value = mock_driver
    mock_load.return_value = valid_dataframe
    mock_process.side_effect = RuntimeError("driver crashed")

    with pytest.raises(RuntimeError):
        filler.run()

    mock_driver.quit.assert_called_once()


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------


from form_filler import build_parser, main  # noqa: E402


def test_parser_requires_input_argument():
    """--input is mandatory; parser exits when missing."""
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_parser_accepts_minimal_args(tmp_path: Path):
    """Only --input is required; defaults fill the rest."""
    parser = build_parser()
    args = parser.parse_args(["--input", str(tmp_path / "in.xlsx")])

    assert args.input == tmp_path / "in.xlsx"
    assert args.headless is None  # not given => no override
    assert args.limit is None


def test_parser_accepts_headless_and_limit(tmp_path: Path):
    """--headless and --limit are parsed correctly."""
    parser = build_parser()
    args = parser.parse_args(
        ["--input", str(tmp_path / "in.xlsx"), "--headless", "--limit", "5"]
    )

    assert args.headless is True
    assert args.limit == 5


def test_parser_no_headless_flag_sets_false(tmp_path: Path):
    """--no-headless explicitly sets headless to False."""
    parser = build_parser()
    args = parser.parse_args(
        ["--input", str(tmp_path / "in.xlsx"), "--no-headless"]
    )

    assert args.headless is False


@patch("form_filler.FormFiller")
@patch("form_filler.load_yaml_config")
def test_main_passes_limit_to_run(mock_load_config, mock_filler_class, tmp_path):
    """main() forwards --limit to FormFiller.run()."""
    mock_load_config.return_value = {
        "target": {"url": "x", "submit_selector": "x", "confirmation_selector": "x"},
        "behavior": {"headless": False},
        "fields": {},
    }
    instance = MagicMock()
    mock_filler_class.return_value = instance

    exit_code = main([
        "--input", str(tmp_path / "in.xlsx"),
        "--limit", "2",
    ])

    assert exit_code == 0
    instance.run.assert_called_once_with(limit=2)


@patch("form_filler.FormFiller")
@patch("form_filler.load_yaml_config")
def test_main_headless_flag_overrides_config(mock_load_config, mock_filler_class, tmp_path):
    """--headless mutates the config dict before FormFiller is constructed."""
    base_config = {
        "target": {"url": "x", "submit_selector": "x", "confirmation_selector": "x"},
        "behavior": {"headless": False},
        "fields": {},
    }
    mock_load_config.return_value = base_config

    main([
        "--input", str(tmp_path / "in.xlsx"),
        "--headless",
    ])

    # FormFiller was built with a config whose headless flag is now True.
    called_config = mock_filler_class.call_args.kwargs["config"]
    assert called_config["behavior"]["headless"] is True
