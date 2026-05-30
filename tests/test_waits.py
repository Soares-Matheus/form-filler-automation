"""Tests for :mod:`automation_core.waits`.

These tests mock the WebDriver and WebDriverWait so they run in
milliseconds and never touch a real browser. The goal is to verify
the *logic* of each helper -- which Selenium API it calls, in which
order, and with which arguments -- not to integration-test Selenium
itself, which already has its own test suite.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from selenium.webdriver.common.by import By

from automation_core.waits import (
    DEFAULT_TIMEOUT,
    wait_and_click,
    wait_and_type,
    wait_for_element,
)


# ---------------------------------------------------------------------------
# wait_for_element
# ---------------------------------------------------------------------------


@patch("automation_core.waits.WebDriverWait")
def test_wait_for_element_returns_the_resolved_element(mock_wdw_class):
    """The element resolved by WebDriverWait.until() is returned to caller."""
    expected_element = MagicMock(name="element")
    mock_wdw_class.return_value.until.return_value = expected_element
    driver = MagicMock(name="driver")

    result = wait_for_element(driver, (By.CSS_SELECTOR, "#firstName"))

    assert result is expected_element
    mock_wdw_class.assert_called_once_with(driver, DEFAULT_TIMEOUT)


@patch("automation_core.waits.WebDriverWait")
def test_wait_for_element_respects_custom_timeout(mock_wdw_class):
    """A custom timeout is forwarded to WebDriverWait."""
    driver = MagicMock(name="driver")

    wait_for_element(driver, (By.ID, "x"), timeout=3.5)

    mock_wdw_class.assert_called_once_with(driver, 3.5)


# ---------------------------------------------------------------------------
# wait_and_click
# ---------------------------------------------------------------------------


@patch("automation_core.waits.WebDriverWait")
def test_wait_and_click_clicks_the_returned_element(mock_wdw_class):
    """The element returned by WebDriverWait is clicked exactly once."""
    element = MagicMock(name="element")
    mock_wdw_class.return_value.until.return_value = element
    driver = MagicMock(name="driver")

    result = wait_and_click(driver, (By.CSS_SELECTOR, "#submit"))

    element.click.assert_called_once()
    assert result is element


# ---------------------------------------------------------------------------
# wait_and_type
# ---------------------------------------------------------------------------


@patch("automation_core.waits.WebDriverWait")
def test_wait_and_type_clears_then_types(mock_wdw_class):
    """By default, the field is cleared before sending keys."""
    element = MagicMock(name="element")
    mock_wdw_class.return_value.until.return_value = element
    driver = MagicMock(name="driver")

    wait_and_type(driver, (By.ID, "firstName"), "Ana")

    element.clear.assert_called_once()
    element.send_keys.assert_called_once_with("Ana")


@patch("automation_core.waits.WebDriverWait")
def test_wait_and_type_skips_clear_when_disabled(mock_wdw_class):
    """clear_first=False does NOT clear the field before typing."""
    element = MagicMock(name="element")
    mock_wdw_class.return_value.until.return_value = element
    driver = MagicMock(name="driver")

    wait_and_type(driver, (By.ID, "x"), "abc", clear_first=False)

    element.clear.assert_not_called()
    element.send_keys.assert_called_once_with("abc")
