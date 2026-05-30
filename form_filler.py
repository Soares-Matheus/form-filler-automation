"""Form Filler Automation -- end-to-end orchestrator + CLI.

This module owns the :class:`FormFiller` class (the "conductor" that
glues every piece in ``automation_core/`` together) and the
command-line entry point :func:`main`.
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from automation_core.driver import build_driver
from automation_core.fields import fill_field
from automation_core.io_utils import (
    export_results,
    load_spreadsheet,
    validate_columns,
)
from automation_core.logging_setup import configure_logger
from automation_core.waits import wait_and_click, wait_for_element


ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = ROOT / "config.yaml"
DEFAULT_OUTPUT_DIR = ROOT / "output"
DEFAULT_LOG_PATH = ROOT / "logs" / "run.log"

# Backoff base (seconds). Attempt N waits BACKOFF_BASE * 2**N before retrying:
# attempt 0 fails -> wait 0.5s, attempt 1 fails -> wait 1s, etc.
BACKOFF_BASE: float = 0.5

# DemoQA fades its confirmation modal in with a short CSS transition.
# wait_for_element returns the moment the modal enters the DOM, which
# is BEFORE the animation finishes -- giving us half-opaque screenshots.
# A brief sleep after the wait keeps the captures sharp.
MODAL_ANIMATION_DELAY: float = 0.4


class FormFiller:
    """Run a spreadsheet-driven form filling pipeline.

    See :func:`main` for the CLI; instantiate this class directly for
    programmatic use.
    """

    def __init__(
        self,
        config: dict,
        input_path: str | Path,
        output_dir: str | Path,
        log_path: str | Path | None = None,
    ) -> None:
        self.config = config
        self.input_path = Path(input_path)
        self.output_dir = Path(output_dir)
        self.screenshots_dir = self.output_dir / "screenshots"
        self.results_path = self.output_dir / "results.xlsx"
        self.logger = configure_logger(log_file=log_path)

        self.field_specs = config["fields"]
        self.target = config["target"]
        self.behavior = config.get("behavior", {})

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, limit: int | None = None, dry_run: bool = False) -> pd.DataFrame:
        """Execute the full pipeline and return the results DataFrame.

        Parameters
        ----------
        limit : int | None, default None
            If given, process only the first ``limit`` rows.
        dry_run : bool, default False
            If True, fill every field but skip the submit click. Useful
            for validating against a real system without creating records.
        """
        df = load_spreadsheet(self.input_path)
        validate_columns(df, list(self.field_specs.keys()))

        if limit is not None:
            df = df.head(limit)

        mode = "dry-run" if dry_run else "live"
        self.logger.info(f"Starting {mode} run over {len(df)} row(s)")

        driver = build_driver(headless=self.behavior.get("headless", False))
        statuses: list[str] = []
        errors: list[str] = []

        try:
            for index, row in df.iterrows():
                status, error = self._process_row(
                    driver, int(index), row.to_dict(), dry_run=dry_run
                )
                statuses.append(status)
                errors.append(error)
        finally:
            driver.quit()

        results_df = df.copy()
        results_df["status"] = statuses
        results_df["error"] = errors

        written_path = export_results(results_df, self.results_path)
        successes = statuses.count("success")
        failures = len(statuses) - successes
        self.logger.info(
            f"Run complete: {successes} succeeded, {failures} failed -- "
            f"results at {written_path}"
        )

        return results_df

    # ------------------------------------------------------------------
    # Per-row helpers
    # ------------------------------------------------------------------

    def _process_row(
        self,
        driver: WebDriver,
        index: int,
        row: dict,
        dry_run: bool = False,
    ) -> tuple[str, str]:
        """Fill, submit (unless ``dry_run``), capture -- with retries.

        ``config.behavior.retries`` controls how many extra attempts a
        failing row gets. Exponential backoff (0.5s, 1s, 2s, 4s, ...)
        spaces them out so transient page hiccups have time to settle.
        """
        retries = int(self.behavior.get("retries", 0))
        last_exception: Exception | None = None

        for attempt in range(retries + 1):
            try:
                self._fill_and_submit(driver, index, row, dry_run=dry_run)
                self.logger.info(f"Row {index}: success")
                return "success", ""
            except Exception as exc:  # noqa: BLE001 -- isolation by design
                last_exception = exc
                is_last_attempt = attempt == retries
                if is_last_attempt:
                    break
                wait = BACKOFF_BASE * (2 ** attempt)
                self.logger.warning(
                    f"Row {index}: attempt {attempt + 1}/{retries + 1} "
                    f"failed: {exc!r}. Retrying in {wait:.1f}s"
                )
                time.sleep(wait)

        # Out of retries. Log, screenshot, return error.
        self.logger.error(
            f"Row {index} failed after {retries + 1} attempt(s): {last_exception!r}"
        )
        try:
            self._capture_screenshot(driver, index, suffix="ERROR")
        except Exception:  # noqa: BLE001
            self.logger.warning(f"Row {index}: failed to capture error screenshot")
        return "error", str(last_exception)

    def _fill_and_submit(
        self,
        driver: WebDriver,
        index: int,
        row: dict,
        dry_run: bool = False,
    ) -> None:
        """One attempt: navigate, fill every field, submit (or skip)."""
        self.logger.info(f"Row {index}: navigating to form")
        driver.get(self.target["url"])

        for column_name, field_spec in self.field_specs.items():
            value = row[column_name]
            self.logger.info(
                f"Row {index}: filling {column_name} "
                f"({field_spec['type']}) = {value!r}"
            )
            fill_field(
                driver,
                field_spec["type"],
                field_spec["selector"],
                value,
            )

        if dry_run:
            self.logger.info(f"Row {index}: dry-run -- skipping submit")
            self._capture_screenshot(driver, index, suffix="DRYRUN")
        else:
            self._submit_and_capture(driver, index)

    def _submit_and_capture(self, driver: WebDriver, index: int) -> None:
        """Submit the form, wait for confirmation, screenshot, dismiss."""
        submit_selector = self.target["submit_selector"]
        confirmation_selector = self.target["confirmation_selector"]

        submit_element = wait_for_element(driver, (By.CSS_SELECTOR, submit_selector))
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", submit_element
        )

        wait_and_click(driver, (By.CSS_SELECTOR, submit_selector))
        wait_for_element(driver, (By.CSS_SELECTOR, confirmation_selector))

        # Let the modal's fade-in finish before capturing. See MODAL_ANIMATION_DELAY.
        time.sleep(MODAL_ANIMATION_DELAY)
        self._capture_screenshot(driver, index)

        try:
            driver.find_element(By.CSS_SELECTOR, "#closeLargeModal").click()
        except Exception:  # noqa: BLE001
            pass

    def _capture_screenshot(
        self,
        driver: WebDriver,
        index: int,
        suffix: str = "",
    ) -> Path:
        """Save a PNG screenshot to ``screenshots/`` and return its path."""
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix_part = f"_{suffix}" if suffix else ""
        filename = f"row_{index}_{timestamp}{suffix_part}.png"
        path = self.screenshots_dir / filename
        driver.save_screenshot(str(path))
        return path


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser. Exposed for unit testing."""
    parser = argparse.ArgumentParser(
        prog="form_filler",
        description="Fill a web form from a spreadsheet, driven by config.yaml.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to the input spreadsheet (.xlsx or .csv).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"Path to the YAML config (default: {DEFAULT_CONFIG_PATH.name}).",
    )
    parser.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Override config.behavior.headless. Use --headless or --no-headless.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N rows (useful for smoke tests).",
    )
    parser.add_argument(
        "--no-submit",
        action="store_true",
        help="Dry-run: fill every field but DO NOT click submit.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Where to write results.xlsx and screenshots/ "
             f"(default: {DEFAULT_OUTPUT_DIR.name}/).",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=DEFAULT_LOG_PATH,
        help=f"Where to persist the log (default: "
             f"{DEFAULT_LOG_PATH.relative_to(ROOT)}).",
    )
    return parser


def load_yaml_config(path: Path) -> dict:
    """Read a YAML file into a dict. Tiny wrapper for explicit testing."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    config = load_yaml_config(args.config)

    if args.headless is not None:
        config.setdefault("behavior", {})["headless"] = args.headless

    filler = FormFiller(
        config=config,
        input_path=args.input,
        output_dir=args.output_dir,
        log_path=args.log_file,
    )
    filler.run(limit=args.limit, dry_run=args.no_submit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
