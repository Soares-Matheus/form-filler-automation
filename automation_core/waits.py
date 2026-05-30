"""Wait helpers for the Form Filler Automation project.

This module wraps Selenium's ``WebDriverWait`` + ``expected_conditions``
API into a small set of high-level helpers. Every interaction with the
page goes through one of these functions -- never a bare ``time.sleep()`` --
so timings stay elastic: fast when the page is fast, patient when it is
slow, and explicit about what we are waiting for.
"""
from __future__ import annotations

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait


DEFAULT_TIMEOUT: float = 10.0
"""Default number of seconds before raising :class:`TimeoutException`."""


# Locator tuple: (by_strategy, selector_value), e.g. (By.CSS_SELECTOR, "#submit").
Locator = tuple[str, str]


def wait_for_element(
    driver: WebDriver,
    locator: Locator,
    timeout: float = DEFAULT_TIMEOUT,
    visible: bool = True,
) -> WebElement:
    """Wait for an element to appear and return it.

    Parameters
    ----------
    driver : WebDriver
        Active Selenium WebDriver instance.
    locator : tuple[str, str]
        Pair of ``(By.<strategy>, selector_string)``.
    timeout : float, default :data:`DEFAULT_TIMEOUT`
        Seconds to wait before raising :class:`TimeoutException`.
    visible : bool, default True
        If True, waits until the element is also visible (rendered with
        non-zero size). If False, waits only for the element to exist
        in the DOM -- useful for hidden inputs.

    Returns
    -------
    WebElement
        The matching element, ready to be inspected or acted upon.

    Raises
    ------
    selenium.common.exceptions.TimeoutException
        If the element does not appear within ``timeout`` seconds.
    """
    wait = WebDriverWait(driver, timeout)
    condition = (
        EC.visibility_of_element_located(locator)
        if visible
        else EC.presence_of_element_located(locator)
    )
    return wait.until(condition)


def wait_and_click(
    driver: WebDriver,
    locator: Locator,
    timeout: float = DEFAULT_TIMEOUT,
) -> WebElement:
    """Wait until an element is clickable and click it.

    Parameters
    ----------
    driver : WebDriver
        Active Selenium WebDriver instance.
    locator : tuple[str, str]
        Pair of ``(By.<strategy>, selector_string)``.
    timeout : float, default :data:`DEFAULT_TIMEOUT`
        Seconds to wait before raising :class:`TimeoutException`.

    Returns
    -------
    WebElement
        The clicked element. Returned so the caller can chain further
        actions if needed (e.g. read its text right after the click).

    Raises
    ------
    selenium.common.exceptions.TimeoutException
        If the element never becomes clickable within the timeout.
    """
    wait = WebDriverWait(driver, timeout)
    element = wait.until(EC.element_to_be_clickable(locator))
    element.click()
    return element


def wait_and_type(
    driver: WebDriver,
    locator: Locator,
    text: str,
    timeout: float = DEFAULT_TIMEOUT,
    clear_first: bool = True,
) -> WebElement:
    """Wait for an input field and type ``text`` into it.

    Parameters
    ----------
    driver : WebDriver
        Active Selenium WebDriver instance.
    locator : tuple[str, str]
        Pair of ``(By.<strategy>, selector_string)``.
    text : str
        Text to type into the field. Sent through ``send_keys``, so
        special values like ``Keys.RETURN`` are honoured if mixed in.
    timeout : float, default :data:`DEFAULT_TIMEOUT`
        Seconds to wait before raising :class:`TimeoutException`.
    clear_first : bool, default True
        If True, clears the current field value before typing. Set to
        False when typing additional characters into a populated field.

    Returns
    -------
    WebElement
        The field that was typed into.

    Raises
    ------
    selenium.common.exceptions.TimeoutException
        If the field never becomes visible within the timeout.
    """
    wait = WebDriverWait(driver, timeout)
    element = wait.until(EC.visibility_of_element_located(locator))
    if clear_first:
        element.clear()
    element.send_keys(text)
    return element
