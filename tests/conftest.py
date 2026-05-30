"""Shared pytest fixtures for the test suite.

``conftest.py`` is auto-discovered by pytest: every fixture defined
here is available to any test in the same directory or below, without
explicit imports. Centralising fixtures here keeps the individual test
files focused on assertions instead of test-data setup.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture
def valid_dataframe() -> pd.DataFrame:
    """Two rows matching the DemoQA field schema.

    Every value is a ``str`` mirrors what :func:`load_spreadsheet`
    is expected to produce. The first row deliberately uses a mobile
    number starting with ``0`` so the leading-zero preservation test
    can detect dtype-inference bugs.
    """
    return pd.DataFrame(
        [
            {
                "first_name": "Ana",
                "last_name": "Souza",
                "email": "ana@example.com",
                "gender": "Female",
                "mobile": "0991234567",  # leading zero on purpose
                "state": "NCR",
            },
            {
                "first_name": "Bruno",
                "last_name": "Lima",
                "email": "bruno@example.com",
                "gender": "Male",
                "mobile": "9990002222",
                "state": "Uttar Pradesh",
            },
        ]
    )


@pytest.fixture
def xlsx_file(tmp_path: Path, valid_dataframe: pd.DataFrame) -> Path:
    """Write :data:`valid_dataframe` to a temporary ``.xlsx`` file.

    Uses pytest's built-in :func:`tmp_path` fixture, which provides a
    fresh directory per test and cleans it up automatically. Each test
    gets its own file — no cross-test pollution.
    """
    path = tmp_path / "records.xlsx"
    valid_dataframe.to_excel(path, index=False)
    return path


@pytest.fixture
def csv_file(tmp_path: Path, valid_dataframe: pd.DataFrame) -> Path:
    """Write :data:`valid_dataframe` to a temporary ``.csv`` file."""
    path = tmp_path / "records.csv"
    valid_dataframe.to_csv(path, index=False)
    return path
