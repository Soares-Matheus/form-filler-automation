"""Field-handler dispatchers for the Form Filler Automation project.

Each handler knows how to fill ONE type of HTML field (text, radio,
dropdown, checkbox, date). The :func:`fill_field` entry point reads
the ``field_type`` from ``config.yaml`` and delegates to the right
handler. The handler-by-name dispatch is what keeps this module
form-agnostic: every form-specific detail (which selector, which
value) lives in ``config.yaml``, never here.
"""
from __future__ import annotations

from typing import Callable

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from automation_core.waits import wait_and_click, wait_and_type, wait_for_element


def fill_text(driver: WebDriver, selector: str, value: str) -> None:
    """Type ``value`` into a text input matched by CSS ``selector``."""
    wait_and_type(driver, (By.CSS_SELECTOR, selector), value)


def fill_radio(driver: WebDriver, selector: str, value: str) -> None:
    """Click the radio whose label text equals ``value``.

    ``selector`` should match every label in the radio group (for the
    DemoQA gender field that is ``"label[for^='gender-radio']"``).
    The handler iterates the matched labels and clicks the one whose
    visible text equals ``value`` (whitespace-trimmed, case-sensitive).

    Raises
    ------
    ValueError
        If no label matching ``value`` is found among the candidates.
    """
    wait_for_element(driver, (By.CSS_SELECTOR, selector))
    candidates = driver.find_elements(By.CSS_SELECTOR, selector)
    target_value = value.strip()
    for label in candidates:
        if label.text.strip() == target_value:
            label.click()
            return
    raise ValueError(
        f"Radio option '{value}' not found among labels matching '{selector}'."
    )


def select_dropdown(driver: WebDriver, selector: str, value: str) -> None:
    """Open a dropdown and click the option whose text equals ``value``.

    Designed for React-Select widgets (DemoQA, MUI, etc.) which are
    NOT native ``<select>`` elements, so ``selenium.support.ui.Select``
    does not work on them. Strategy:

    1. Click the container at ``selector`` to expand the option list.
    2. Click the option located by its visible text (XPath).
    """
    wait_and_click(driver, (By.CSS_SELECTOR, selector))
    option_xpath = f"//div[normalize-space()='{value}']"
    wait_and_click(driver, (By.XPATH, option_xpath))


def fill_checkbox(driver: WebDriver, selector: str, value: str) -> None:
    """Click a checkbox iff ``value`` is one of the accepted truthy strings.

    Truthy values: ``'true'``, ``'yes'``, ``'1'``, ``'checked'`` (case
    and whitespace insensitive). Anything else is treated as "leave the
    checkbox alone" -- the handler is a no-op.
    """
    truthy = {"true", "yes", "1", "checked"}
    if str(value).strip().lower() not in truthy:
        return
    wait_and_click(driver, (By.CSS_SELECTOR, selector))


def fill_date(driver: WebDriver, selector: str, value: str) -> None:
    """Type a date string into a date input.

    No parsing or reformatting is done -- the spreadsheet is expected
    to provide the date in the format the target field accepts
    (e.g. ``'15 Jan 1990'`` for DemoQA, ``'1990-01-15'`` for ISO inputs).
    """
    wait_and_type(driver, (By.CSS_SELECTOR, selector), value)


# Dispatch table. Adding a new field type means:
#   1. Write a new fill_<type>(driver, selector, value) function above.
#   2. Add an entry to this dict.
# No other change needed downstream -- fill_field() picks it up.
HANDLERS: dict[str, Callable[[WebDriver, str, str], None]] = {
    "text": fill_text,
    "radio": fill_radio,
    "dropdown": select_dropdown,
    "checkbox": fill_checkbox,
    "date": fill_date,
}


def fill_field(
    driver: WebDriver,
    field_type: str,
    selector: str,
    value: str,
) -> None:
    """Fill one form field by dispatching to the matching handler.

    Parameters
    ----------
    driver : WebDriver
        Active Selenium WebDriver instance.
    field_type : str
        One of the keys in :data:`HANDLERS` (e.g. ``"text"``).
    selector : str
        CSS selector pointing to the field.
    value : str
        Value to fill. Always a string -- the I/O layer guarantees
        every cell in the input spreadsheet is read as ``str``.

    Raises
    ------
    ValueError
        If ``field_type`` is not registered in :data:`HANDLERS`.
    """
    handler = HANDLERS.get(field_type)
    if handler is None:
        raise ValueError(
            f"Unsupported field type: '{field_type}'. "
            f"Registered types: {sorted(HANDLERS)}."
        )
    handler(driver, selector, value)
