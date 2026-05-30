"""Tests for :mod:`form_filler`."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from form_filler import FormFiller, build_parser, main


@pytest.fixture
def base_config() -> dict:
    return {
        "target": {
            "url": "https://demoqa.com/automation-practice-form",
            "submit_selector": "#submit",
            "confirmation_selector": ".modal-content",
        },
        "behavior": {"headless": True, "retries": 0},
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
    return FormFiller(
        config=base_config,
        input_path=tmp_path / "in.xlsx",
        output_dir=tmp_path / "out",
        log_path=tmp_path / "logs" / "run.log",
    )


def test_init_sets_paths_and_config(filler: FormFiller, tmp_path: Path) -> None:
    assert filler.input_path == tmp_path / "in.xlsx"
    assert filler.output_dir == tmp_path / "out"
    assert filler.screenshots_dir == tmp_path / "out" / "screenshots"
    assert filler.results_path == tmp_path / "out" / "results.xlsx"
    assert "first_name" in filler.field_specs


# ----- _process_row: success / failure / retry ----------------------------


@patch("form_filler.FormFiller._fill_and_submit")
def test_process_row_success_returns_success_status(
    mock_fill_submit, filler: FormFiller
) -> None:
    driver = MagicMock()
    row = {"first_name": "Ana"}

    status, error = filler._process_row(driver, 0, row)

    assert status == "success"
    assert error == ""


@patch("form_filler.FormFiller._capture_screenshot")
@patch("form_filler.FormFiller._fill_and_submit")
def test_process_row_isolates_failure(
    mock_fill_submit, mock_screenshot, filler: FormFiller
) -> None:
    mock_fill_submit.side_effect = RuntimeError("boom")
    driver = MagicMock()

    status, error = filler._process_row(driver, 3, {})

    assert status == "error"
    assert "boom" in error


@patch("form_filler.time.sleep")  # don't actually wait during tests
@patch("form_filler.FormFiller._capture_screenshot")
@patch("form_filler.FormFiller._fill_and_submit")
def test_process_row_retries_until_success(
    mock_fill_submit, mock_screenshot, mock_sleep,
    base_config: dict, tmp_path: Path,
) -> None:
    """A row that fails twice then succeeds is reported as success."""
    base_config["behavior"]["retries"] = 2
    filler = FormFiller(base_config, tmp_path / "in.xlsx", tmp_path / "out")
    mock_fill_submit.side_effect = [RuntimeError("a"), RuntimeError("b"), None]

    status, error = filler._process_row(MagicMock(), 0, {})

    assert status == "success"
    assert mock_fill_submit.call_count == 3


@patch("form_filler.time.sleep")
@patch("form_filler.FormFiller._capture_screenshot")
@patch("form_filler.FormFiller._fill_and_submit")
def test_process_row_gives_up_after_retries(
    mock_fill_submit, mock_screenshot, mock_sleep,
    base_config: dict, tmp_path: Path,
) -> None:
    """Persistent failure exhausts retries and returns ('error', msg)."""
    base_config["behavior"]["retries"] = 2
    filler = FormFiller(base_config, tmp_path / "in.xlsx", tmp_path / "out")
    mock_fill_submit.side_effect = RuntimeError("persistent")

    status, error = filler._process_row(MagicMock(), 0, {})

    assert status == "error"
    assert "persistent" in error
    assert mock_fill_submit.call_count == 3  # initial + 2 retries


# ----- _fill_and_submit: dry-run behaviour --------------------------------


@patch("form_filler.fill_field")
@patch("form_filler.FormFiller._submit_and_capture")
@patch("form_filler.FormFiller._capture_screenshot")
def test_fill_and_submit_dry_run_skips_submit(
    mock_screenshot, mock_submit, mock_fill, filler: FormFiller
) -> None:
    """dry_run=True takes a screenshot but never calls _submit_and_capture."""
    driver = MagicMock()
    row = {k: "x" for k in filler.field_specs}

    filler._fill_and_submit(driver, 0, row, dry_run=True)

    mock_submit.assert_not_called()
    mock_screenshot.assert_called_once()  # the DRYRUN screenshot


@patch("form_filler.fill_field")
@patch("form_filler.FormFiller._submit_and_capture")
def test_fill_and_submit_live_mode_submits(
    mock_submit, mock_fill, filler: FormFiller
) -> None:
    """dry_run=False routes through the normal submit path."""
    driver = MagicMock()
    row = {k: "x" for k in filler.field_specs}

    filler._fill_and_submit(driver, 0, row, dry_run=False)

    mock_submit.assert_called_once_with(driver, 0)


# ----- run(): orchestration ----------------------------------------------


@patch("form_filler.export_results")
@patch("form_filler.build_driver")
@patch("form_filler.FormFiller._process_row")
@patch("form_filler.load_spreadsheet")
def test_run_appends_status_and_error_columns(
    mock_load, mock_process, mock_build_driver, mock_export,
    filler: FormFiller, valid_dataframe: pd.DataFrame,
) -> None:
    mock_load.return_value = valid_dataframe
    mock_process.side_effect = [("success", ""), ("error", "timeout")]
    mock_build_driver.return_value = MagicMock()

    result_df = filler.run()

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
    longer = pd.concat([valid_dataframe] * 5, ignore_index=True)
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
def test_run_forwards_dry_run_to_process_row(
    mock_load, mock_process, mock_build_driver, mock_export,
    filler: FormFiller, valid_dataframe: pd.DataFrame,
) -> None:
    mock_load.return_value = valid_dataframe
    mock_process.return_value = ("success", "")
    mock_build_driver.return_value = MagicMock()

    filler.run(dry_run=True)

    # Every call gets dry_run=True forwarded as a keyword arg.
    for call in mock_process.call_args_list:
        assert call.kwargs["dry_run"] is True


@patch("form_filler.export_results")
@patch("form_filler.build_driver")
@patch("form_filler.FormFiller._process_row")
@patch("form_filler.load_spreadsheet")
def test_run_quits_driver_even_on_exception(
    mock_load, mock_process, mock_build_driver, mock_export,
    filler: FormFiller, valid_dataframe: pd.DataFrame,
) -> None:
    mock_driver = MagicMock()
    mock_build_driver.return_value = mock_driver
    mock_load.return_value = valid_dataframe
    mock_process.side_effect = RuntimeError("driver crashed")

    with pytest.raises(RuntimeError):
        filler.run()

    mock_driver.quit.assert_called_once()


# ----- CLI parser ---------------------------------------------------------


def test_parser_requires_input_argument():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_parser_accepts_minimal_args(tmp_path: Path):
    parser = build_parser()
    args = parser.parse_args(["--input", str(tmp_path / "in.xlsx")])
    assert args.input == tmp_path / "in.xlsx"
    assert args.headless is None
    assert args.limit is None
    assert args.no_submit is False


def test_parser_no_submit_flag(tmp_path: Path):
    parser = build_parser()
    args = parser.parse_args(["--input", str(tmp_path / "in.xlsx"), "--no-submit"])
    assert args.no_submit is True


def test_parser_headless_and_limit(tmp_path: Path):
    parser = build_parser()
    args = parser.parse_args(
        ["--input", str(tmp_path / "in.xlsx"), "--headless", "--limit", "5"]
    )
    assert args.headless is True
    assert args.limit == 5


@patch("form_filler.FormFiller")
@patch("form_filler.load_yaml_config")
def test_main_forwards_dry_run(mock_load_config, mock_filler_class, tmp_path):
    mock_load_config.return_value = {
        "target": {"url": "x", "submit_selector": "x", "confirmation_selector": "x"},
        "behavior": {"headless": False},
        "fields": {},
    }
    instance = MagicMock()
    mock_filler_class.return_value = instance

    main(["--input", str(tmp_path / "in.xlsx"), "--no-submit"])

    instance.run.assert_called_once_with(limit=None, dry_run=True)


@patch("form_filler.FormFiller")
@patch("form_filler.load_yaml_config")
def test_main_headless_overrides_config(mock_load_config, mock_filler_class, tmp_path):
    mock_load_config.return_value = {
        "target": {"url": "x", "submit_selector": "x", "confirmation_selector": "x"},
        "behavior": {"headless": False},
        "fields": {},
    }

    main(["--input", str(tmp_path / "in.xlsx"), "--headless"])

    called_config = mock_filler_class.call_args.kwargs["config"]
    assert called_config["behavior"]["headless"] is True
