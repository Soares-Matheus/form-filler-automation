"""Browser factory for the Form Filler Automation project.

This module wraps the construction of a Chrome WebDriver with the
anti-detection options every modern automation project needs:

- Removes the "Chrome is being controlled by automated software" banner.
- Hides the ``navigator.webdriver`` flag that JavaScript code uses to detect bots.
- Forces a human-sized window so the page never renders in a tiny viewport.

Selenium 4.6+ ships with Selenium Manager, which auto-downloads the
matching ChromeDriver on first use -- no manual binary management.
"""
from __future__ import annotations

from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def build_driver(
    headless: bool = False,
    window_size: tuple[int, int] = (1920, 1080),
) -> webdriver.Chrome:
    """Create a Chrome WebDriver configured with anti-detection options.

    Parameters
    ----------
    headless : bool, default False
        If True, runs Chrome without a visible window. Useful for
        unattended runs and CI; leave False during development so you
        can watch the bot drive the page.
    window_size : tuple[int, int], default (1920, 1080)
        Window dimensions in pixels. The default mirrors a common
        full-HD desktop resolution to look like normal human usage --
        bot detectors flag tiny or off-spec viewports.

    Returns
    -------
    selenium.webdriver.Chrome
        A fully configured Chrome WebDriver instance, ready to navigate.
    """
    options = Options()

    # Remove the "Chrome is being controlled by automated test software"
    # info bar and the automation extension that ships with it.
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # Hide the navigator.webdriver flag that JS code uses to detect bots.
    options.add_argument("--disable-blink-features=AutomationControlled")

    # Force a human-sized window.
    width, height = window_size
    options.add_argument(f"--window-size={width},{height}")

    # Quiet down noisy Chrome log output on the console.
    options.add_argument("--log-level=3")

    if headless:
        # The "new" headless mode (Chrome 109+) is closer to a real
        # browser than the legacy --headless flag.
        options.add_argument("--headless=new")

    # Selenium 4.6+ ships with Selenium Manager, which auto-downloads
    # the right ChromeDriver for the installed Chrome. No extra setup.
    driver = webdriver.Chrome(options=options)

    return driver
