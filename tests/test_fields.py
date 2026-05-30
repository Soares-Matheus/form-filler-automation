"""Tests for :mod:`automation_core.fields`.

The wait helpers are patched so the tests run in milliseconds without
a real browser. Each test asserts a specific behavioural contract of
a single handler.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from selenium.webdriver.common.by import By

from automation_core.fields import (
    fill_checkbox,
    fill_date,
    fill_field,
    fill_radio,
    fill_text,
    select_dropdown,
)


# ---------------------------------------------------------------------------
# fill_text
# ---------------------------------------------------------------------------


@patch("automation_core.fields.wait_and_type")
def test_fill_text_calls_wait_and_type(mock_type):
    """fill_text delegates straight to wait_and_type with a CSS locator."""
    driver = MagicMock()

    fill_text(driver, "#firstName", "Ana")

    mock_type.assert_called_once_with(
        driver, (By.CSS_SELECTOR, "#firstName"), "Ana"
    )


# ---------------------------------------------------------------------------
# fill_radio
# ---------------------------------------------------------------------------


@patch("automation_core.fields.wait_for_element")
def test_fill_radio_clicks_label_with_matching_text(mock_wait):
    """Only the label whose text equals ``value`` is clicked."""
    male = MagicMock(name="label_male")
    male.text = "Male"
    female = MagicMock(name="label_female")
    female.text = "Female"
    driver = MagicMock()
    driver.find_elements.return_value = [male, female]

    fill_radio(driver, "label[for^='gender-radio']", "Female")

    female.click.assert_called_once()
    male.click.assert_not_called()


@patch("automation_core.fields.wait_for_element")
def test_fill_radio_raises_when_value_not_found(mock_wait):
    """If no label matches the value, a ValueError is raised."""
    label = MagicMock()
    label.text = "Male"
    driver = MagicMock()
    driver.find_elements.return_value = [label]

    with pytest.raises(ValueError) as exc_info:
        fill_radio(driver, "label[for^='gender-radio']", "Other")

    assert "Other" in str(exc_info.value)


# ---------------------------------------------------------------------------
# select_dropdown
# ---------------------------------------------------------------------------


@patch("automation_core.fields.wait_and_click")
def test_select_dropdown_clicks_container_then_option(mock_click):
    """Dropdown is opened first, then the option matching value is clicked."""
    driver = MagicMock()

    select_dropdown(driver, "#state", "NCR")

    assert mock_click.call_count == 2
    # First call opens the dropdown container.
    first_args, _ = mock_click.call_args_list[0]
    assert first_args == (driver, (By.CSS_SELECTOR, "#state"))
    # Second call clicks the option located by visible text.
    second_args, _ = mock_click.call_args_list[1]
    by_strategy, xpath = second_args[1]
    assert by_strategy == By.XPATH
    assert "NCR" in xpath


# ---------------------------------------------------------------------------
# fill_checkbox
# ---------------------------------------------------------------------------


@patch("automation_core.fields.wait_and_click")
def test_fill_checkbox_clicks_when_truthy(mock_click):
    """Truthy strings ('yes', 'true', '1', 'checked') trigger a click."""
    driver = MagicMock()

    fill_checkbox(driver, "#agree", "yes")

    mock_click.assert_called_once_with(driver, (By.CSS_SELECTOR, "#agree"))


@patch("automation_core.fields.wait_and_click")
def test_fill_checkbox_skips_when_falsy(mock_click):
    """Falsy/unknown values leave the checkbox untouched."""
    driver = MagicMock()

    fill_checkbox(driver, "#agree", "no")

    mock_click.assert_not_called()


# ---------------------------------------------------------------------------
# fill_date
# ---------------------------------------------------------------------------


@patch("automation_core.fields.wait_and_type")
def test_fill_date_types_the_value_verbatim(mock_type):
    """fill_date is a thin wrapper around wait_and_type -- no parsing."""
    driver = MagicMock()

    fill_date(driver, "#dateOfBirth", "15 Jan 1990")

    mock_type.assert_called_once_with(
        driver, (By.CSS_SELECTOR, "#dateOfBirth"), "15 Jan 1990"
    )


# ---------------------------------------------------------------------------
# fill_field (dispatcher)
# ---------------------------------------------------------------------------


def test_fill_field_dispatches_to_registered_handler():
    """fill_field looks up the handler by name and calls it."""
    driver = MagicMock()
    mock_handler = MagicMock()

    with patch.dict("automation_core.fields.HANDLERS", {"text": mock_handler}):
        fill_field(driver, "text", "#firstName", "Ana")

    mock_handler.assert_called_once_with(driver, "#firstName", "Ana")


def test_fill_field_raises_for_unknown_field_type():
    """An unregistered field type raises ValueError mentioning the type."""
    driver = MagicMock()

    with pytest.raises(ValueError) as exc_info:
        fill_field(driver, "carousel", "#x", "value")

    assert "carousel" in str(exc_info.value)
