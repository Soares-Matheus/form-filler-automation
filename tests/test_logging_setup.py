"""Tests for :mod:`automation_core.logging_setup`.

These tests verify the public behavioural contract of
:func:`configure_logger`: returned type, attached handlers, file
writing, idempotency, level handling.
"""
from __future__ import annotations

import logging
from pathlib import Path

from automation_core.logging_setup import (
    DEFAULT_LEVEL,
    DEFAULT_LOGGER_NAME,
    configure_logger,
)


def test_configure_logger_returns_a_logger_with_expected_name():
    """The function returns a Logger instance with the requested name."""
    logger = configure_logger(name="test_basic_logger")

    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_basic_logger"


def test_configure_logger_uses_default_name_when_none_is_given():
    """When called bare, the default logger name is used."""
    logger = configure_logger()

    assert logger.name == DEFAULT_LOGGER_NAME


def test_console_handler_is_a_rich_handler_when_no_file_is_given():
    """Without a log_file, only the RichHandler is attached."""
    logger = configure_logger(name="test_console_only")

    handler_types = [type(h).__name__ for h in logger.handlers]
    assert "RichHandler" in handler_types
    assert "FileHandler" not in handler_types


def test_file_handler_is_attached_when_log_file_is_given(tmp_path: Path):
    """Passing a log_file adds a FileHandler alongside the console one."""
    log_file = tmp_path / "test.log"

    logger = configure_logger(name="test_file_handler", log_file=log_file)

    handler_types = [type(h).__name__ for h in logger.handlers]
    assert "FileHandler" in handler_types


def test_parent_directories_of_log_file_are_created(tmp_path: Path):
    """If the log_file path has missing parent dirs, they are created."""
    log_file = tmp_path / "nested" / "dir" / "run.log"

    configure_logger(name="test_parent_dirs", log_file=log_file)

    assert log_file.parent.exists()


def test_log_messages_are_written_to_the_file(tmp_path: Path):
    """A logger.info() call ends up inside the configured log_file."""
    log_file = tmp_path / "actual.log"
    logger = configure_logger(name="test_file_writes", log_file=log_file)

    logger.info("hello world")
    for handler in logger.handlers:
        handler.flush()

    content = log_file.read_text(encoding="utf-8")
    assert "hello world" in content


def test_configure_logger_is_idempotent():
    """A second call does not duplicate handlers on the same logger."""
    logger1 = configure_logger(name="test_idempotent")
    initial_count = len(logger1.handlers)

    logger2 = configure_logger(name="test_idempotent")

    assert logger1 is logger2  # same logger object
    assert len(logger2.handlers) == initial_count  # no duplicates


def test_configure_logger_respects_custom_level():
    """A custom level is applied to the logger."""
    logger = configure_logger(name="test_level", level=logging.DEBUG)

    assert logger.level == logging.DEBUG
