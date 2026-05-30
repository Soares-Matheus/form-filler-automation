"""Tests for :mod:`automation_core.io_utils`.

Each test follows the Arrange-Act-Assert pattern:

1. Arrange — prepare inputs (often via a fixture).
2. Act — call the function under test.
3. Assert — verify the observable outcome.

These tests are written BEFORE the implementation (red phase of TDD).
They will fail with ``NotImplementedError`` until the body of each
function in ``io_utils.py`` is written.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from automation_core.io_utils import (
    SUPPORTED_EXTENSIONS,
    load_spreadsheet,
    validate_columns,
)


# ---------------------------------------------------------------------------
# load_spreadsheet
# ---------------------------------------------------------------------------


def test_load_spreadsheet_reads_xlsx(xlsx_file: Path) -> None:
    """A ``.xlsx`` file is parsed into a DataFrame with the expected rows."""
    df = load_spreadsheet(xlsx_file)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert df.iloc[0]["first_name"] == "Ana"
    assert df.iloc[1]["first_name"] == "Bruno"


def test_load_spreadsheet_reads_csv(csv_file: Path) -> None:
    """A ``.csv`` file is parsed into a DataFrame with the expected rows."""
    df = load_spreadsheet(csv_file)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert df.iloc[0]["first_name"] == "Ana"
    assert df.iloc[1]["first_name"] == "Bruno"


def test_load_spreadsheet_preserves_leading_zeros(xlsx_file: Path) -> None:
    """Leading zeros on numeric-looking columns survive the round-trip.

    Without explicit ``dtype=str``, pandas infers ``int64`` for columns
    containing only digits and silently strips the leading zero. This
    test pins the contract.
    """
    df = load_spreadsheet(xlsx_file)

    assert df.iloc[0]["mobile"] == "0991234567"


def test_load_spreadsheet_strips_whitespace(tmp_path: Path) -> None:
    """Leading and trailing whitespace is stripped from every string cell."""
    raw = pd.DataFrame([{"first_name": "  Ana  ", "last_name": " Souza"}])
    path = tmp_path / "whitespace.xlsx"
    raw.to_excel(path, index=False)

    df = load_spreadsheet(path)

    assert df.iloc[0]["first_name"] == "Ana"
    assert df.iloc[0]["last_name"] == "Souza"


def test_load_spreadsheet_raises_for_unknown_extension(tmp_path: Path) -> None:
    """An unsupported extension raises :class:`ValueError`."""
    path = tmp_path / "data.txt"
    path.write_text("first_name\nAna\n", encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        load_spreadsheet(path)

    # The error message should mention the offending extension so the
    # user immediately knows what to fix.
    assert ".txt" in str(exc_info.value)


def test_load_spreadsheet_raises_for_missing_file(tmp_path: Path) -> None:
    """A non-existent path raises :class:`FileNotFoundError`."""
    path = tmp_path / "does_not_exist.xlsx"

    with pytest.raises(FileNotFoundError):
        load_spreadsheet(path)


# ---------------------------------------------------------------------------
# validate_columns
# ---------------------------------------------------------------------------


def test_validate_columns_passes_when_all_present(
    valid_dataframe: pd.DataFrame,
) -> None:
    """When every expected column is present, the function returns ``None``."""
    result = validate_columns(
        valid_dataframe,
        expected=["first_name", "email", "mobile"],
    )

    assert result is None


def test_validate_columns_raises_when_column_missing(
    valid_dataframe: pd.DataFrame,
) -> None:
    """Missing columns trigger a ``ValueError`` that names every offender."""
    expected = ["first_name", "email", "missing_one", "missing_two"]

    with pytest.raises(ValueError) as exc_info:
        validate_columns(valid_dataframe, expected)

    message = str(exc_info.value)
    assert "missing_one" in message
    assert "missing_two" in message


# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------


def test_supported_extensions_contract() -> None:
    """The public extension contract must keep ``.xlsx`` and ``.csv``."""
    assert ".xlsx" in SUPPORTED_EXTENSIONS
    assert ".csv" in SUPPORTED_EXTENSIONS
