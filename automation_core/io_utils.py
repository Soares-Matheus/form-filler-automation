"""I/O utilities for the Form Filler Automation project.

This module owns every interaction with spreadsheet files:

- Reading input (``.xlsx`` / ``.csv``) into a pandas ``DataFrame``.
- Validating that the spreadsheet matches the expected schema.
- Exporting the run results back to a spreadsheet (added in a later stage).

Keeping all file I/O concentrated in one module isolates the rest of
the codebase from file-format details, makes the rules around dtype
handling explicit in a single place, and keeps the unit tests focused.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".xlsx", ".csv"})
"""File extensions accepted by :func:`load_spreadsheet`.

Defined at module level as a single source of truth. Adding a new
format (e.g., ``.ods``) only requires touching this constant and the
dispatch inside :func:`load_spreadsheet`.
"""


def load_spreadsheet(path: str | Path) -> pd.DataFrame:
    """Load a spreadsheet file into a pandas ``DataFrame``.

    The file format is detected from the path extension. Every column
    is read as a string (``dtype=str``) to preserve leading zeros --
    critical for phone numbers, ZIP codes, document IDs and similar
    fields where pandas' default type inference would silently corrupt
    the data (e.g., ``"0991"`` becoming ``991``).

    Whitespace is stripped from every string cell to defend against
    invisible trailing or leading spaces that Excel users often paste
    in by accident. Empty cells are normalised to empty strings rather
    than ``NaN`` so downstream code can treat every value as ``str``.

    Parameters
    ----------
    path : str | Path
        Absolute or relative path to the input file.
        Accepted extensions are listed in :data:`SUPPORTED_EXTENSIONS`.

    Returns
    -------
    pandas.DataFrame
        DataFrame whose every cell is a stripped ``str``.

    Raises
    ------
    FileNotFoundError
        If ``path`` does not point to an existing file.
    ValueError
        If the file extension is not in :data:`SUPPORTED_EXTENSIONS`.
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    extension = path.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file extension '{extension}'. "
            f"Supported extensions are: {sorted(SUPPORTED_EXTENSIONS)}."
        )

    # Dispatch by extension. dtype=str forces every column to be read
    # as a string so leading zeros and IDs survive intact.
    if extension == ".xlsx":
        df = pd.read_excel(path, dtype=str)
    else:  # .csv -- only remaining option after the guard above
        df = pd.read_csv(path, dtype=str)

    # Empty cells arrive as NaN (float) even with dtype=str. Normalise
    # them to empty strings so downstream code can treat every value
    # as a str without isinstance() checks scattered everywhere.
    df = df.fillna("")

    # Strip whitespace from every cell. .map() applies element-wise
    # across the whole DataFrame in pandas 2.x (it replaced the now
    # deprecated .applymap()).
    df = df.map(str.strip)

    return df


def validate_columns(df: pd.DataFrame, expected: list[str]) -> None:
    """Ensure ``df`` contains every column listed in ``expected``.

    This is a fail-fast guard: it must be called *before* the browser
    is opened, so a missing column in the input spreadsheet aborts the
    run with a clear, actionable error message instead of blowing up
    halfway through processing rows.

    The match is **case-sensitive and exact** -- no fuzzy or
    case-insensitive matching. This keeps the contract between the
    spreadsheet and ``config.yaml`` strict and explicit; a typo in
    either side is treated as a real error, not silently tolerated.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame returned by :func:`load_spreadsheet`.
    expected : list[str]
        Column names that must be present. Typically derived from the
        keys of the ``fields`` section in ``config.yaml``.

    Raises
    ------
    ValueError
        If one or more expected columns are missing from ``df``.
        The error message lists every missing column to make the
        problem actionable in a single read.
    """
    # Convert to a set for O(1) membership checks. Doing 'col in df.columns'
    # would be O(n) per lookup, which becomes O(n*m) inside the comprehension.
    present = set(df.columns)

    # Iterate 'expected' (a list) instead of using set difference, so the
    # missing columns are reported in the exact order the caller declared
    # them -- typically the order of fields in config.yaml. Predictable
    # output makes the error message scannable.
    missing = [column for column in expected if column not in present]

    if missing:
        raise ValueError(
            f"Required columns missing from spreadsheet: {missing}. "
            f"Present columns: {sorted(present)}."
        )
