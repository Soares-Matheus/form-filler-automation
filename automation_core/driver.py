"""Browser factory for the Form Filler Automation project.

This module wraps the construction of a Chrome WebDriver with the
anti-detection options every modern automation project needs:

- Removes the "Chrome is being controlled by automated software" banner.
- Hides the ``navigator.webdriver`` flag that JavaScript code uses to detect bots.
- Forces a human-sized window so the page never renders in a tiny viewport.
- Silences both the chromedriver and Chrome stderr to keep the console clean.

Selenium 4.6+ ships with Selenium Manager, which auto-downloads the
matching ChromeDriver on first use -- no manual binary management.
"""
from __future__ import annotations

import os
import subprocess
import sys
from contextlib import contextmanager
from typing import Iterator

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


@contextmanager
def _silence_stderr() -> Iterator[None]:
    """Temporarily redirect file descriptor 2 (stderr) to the null device.

    Chrome inherits the Python process' stderr and uses it to print
    the ``DevTools listening on ws://127.0.0.1:...`` banner at startup.
    Selenium's :class:`Service` ``log_output`` only catches the
    *chromedriver* process; Chrome itself bypasses it. To silence the
    banner for good, we redirect at the OS-level file descriptor while
    the driver is being constructed, then restore stderr afterwards so
    the rest of the program's logging is unaffected.
    """
    sys.stderr.flush()
    saved_stderr_fd = os.dup(2)
    devnull_fd = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull_fd, 2)
        yield
    finally:
        os.dup2(saved_stderr_fd, 2)
        os.close(saved_stderr_fd)
        os.close(devnull_fd)


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

    # Quiet down Chrome's own log verbosity. This DOES NOT cover the
    # "DevTools listening on..." banner (see _silence_stderr below).
    options.add_argument("--log-level=3")

    if headless:
        # The "new" headless mode (Chrome 109+) is closer to a real
        # browser than the legacy --headless flag.
        options.add_argument("--headless=new")

    # Silence the chromedriver process' own logs. Necessary but not
    # sufficient -- Chrome itself still prints to stderr.
    service = Service(log_output=subprocess.DEVNULL)

    # Selenium 4.6+ ships with Selenium Manager, which auto-downloads
    # the right ChromeDriver for the installed Chrome. No extra setup.
    # The stderr redirect catches the DevTools banner that Chrome emits
    # *during* driver construction, then restores stderr immediately.
    with _silence_stderr():
        driver = webdriver.Chrome(service=service, options=options)

    return driver
