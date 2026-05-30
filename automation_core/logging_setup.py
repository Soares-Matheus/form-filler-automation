"""Logging configuration for the Form Filler Automation project.

This module owns the construction of the project's logger. It wraps
Python's stdlib :mod:`logging` with a coloured console handler (via
the ``rich`` library) and an optional file handler so every run
leaves both a visible trail on the terminal and a permanent record
on disk.

The configuration is idempotent: calling :func:`configure_logger`
twice with the same name reuses the same logger instance and
replaces its handlers in-place, instead of stacking duplicates that
would cause every log line to be printed twice.
"""
from __future__ import annotations

import logging
from pathlib import Path

from rich.logging import RichHandler


DEFAULT_LOGGER_NAME: str = "form_filler"
"""Name used when the caller does not pass one explicitly."""

DEFAULT_LEVEL: int = logging.INFO
"""Minimum severity emitted when the caller does not override it."""


def configure_logger(
    name: str = DEFAULT_LOGGER_NAME,
    log_file: str | Path | None = None,
    level: int = DEFAULT_LEVEL,
) -> logging.Logger:
    """Configure and return the project logger.

    Parameters
    ----------
    name : str, default :data:`DEFAULT_LOGGER_NAME`
        Logger name. Re-calling this function with the same name
        returns the same logger and replaces its handlers in-place,
        so configuration is idempotent.
    log_file : str | Path | None, default None
        If given, every log record is also written to this file. The
        parent directory is created on demand so the caller does not
        have to ``mkdir`` it manually.
    level : int, default :data:`DEFAULT_LEVEL`
        Minimum severity to emit (e.g. :data:`logging.DEBUG`).

    Returns
    -------
    logging.Logger
        A configured logger with a :class:`rich.logging.RichHandler`
        on the console and -- when ``log_file`` is set -- a plain
        :class:`logging.FileHandler` writing to disk.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Clear any previously attached handlers so a second call does not
    # produce duplicated log lines. This is the standard idempotency
    # pattern for stdlib loggers.
    logger.handlers.clear()

    # ---- Console handler ------------------------------------------------
    # RichHandler gives us colours, level icons and proper traceback
    # rendering with zero extra config.
    console_handler = RichHandler(
        rich_tracebacks=True,
        show_path=False,  # keep the console clean -- the file copy keeps
                          # the full origin path for forensic debugging
    )
    console_handler.setLevel(level)
    logger.addHandler(console_handler)

    # ---- File handler (optional) ---------------------------------------
    if log_file is not None:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(levelname)-8s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(file_handler)

    # Stop log records from bubbling up to the root logger -- otherwise
    # the console line would print twice (once via rich, once via root).
    logger.propagate = False

    return logger
