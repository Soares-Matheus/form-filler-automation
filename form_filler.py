"""Form Filler Automation -- end-to-end orchestrator + CLI.

This module owns the :class:`FormFiller` class (the "conductor" that
glues every piece in ``automation_core/`` together) and the
command-line entry point :func:`main`. Running

::

    python form_filler.py --input data/sample_input.xlsx

reads ``config.yaml``, runs the pipeline against the configured form,
and writes ``output/results.xlsx`` plus per-row screenshots.
"""
from __future__ import annotations

import argparse
import sys
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


# ---------------------------------------------------------------------------
# Default paths (relative to the project root)
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = ROOT / "config.yaml"
DEFAULT_OUTPUT_DIR = ROOT / "output"
DEFAULT_LOG_PATH = ROOT / "logs" / "run.log"


# ---------------------------------------------------------------------------
# FormFiller class
# ---------------------------------------------------------------------------


class FormFiller:
    """Run a spreadsheet-driven form filling pipeline.

    Parameters
    ----------
    config : dict
        Parsed ``config.yaml``. Must contain ``target`` and ``fields``
        sections; ``behavior`` is optional.
    input_path : str | Path
        Path to the input spreadsheet (.xlsx or .csv).
    output_dir : str | Path
        Directory where ``results.xlsx`` and the ``screenshots/`` sub-
        directory are written. Created on demand.
    log_path : str | Path | None, default None
        Optional path to the persistent log file. If given, every log
        record is duplicated to disk in addition to the rich console.
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

    def run(self, limit: int | None = None) -> pd.DataFrame:
        """Execute the full pipeline and return the results DataFrame."""
        df = load_spreadsheet(self.input_path)
        validate_columns(df, list(self.field_specs.keys()))

        if limit is not None:
            df = df.head(limit)

        self.logger.info(f"Starting run over {len(df)} row(s)")

        driver = build_driver(headless=self.behavior.get("headless", False))
        statuses: list[str] = []
        errors: list[str] = []

        try:
            for index, row in df.iterrows():
                status, error = self._process_row(driver, int(index), row.to_dict())
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
    ) -> tuple[str, str]:
        """Fill, submit and capture one row. Failures are isolated."""
        try:
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

            self._submit_and_capture(driver, index)
            self.logger.info(f"Row {index}: success")
            return "success", ""
        except Exception as exc:  # noqa: BLE001 -- isolation by design
            self.logger.error(f"Row {index} failed: {exc!r}")
            try:
                self._capture_screenshot(driver, index, suffix="ERROR")
            except Exception:  # noqa: BLE001
                self.logger.warning(f"Row {index}: failed to capture error screenshot")
            return "error", str(exc)

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
        help="Override config.behavior.headless. "
             "Use --headless or --no-headless.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N rows (useful for smoke tests).",
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
    """Entry point.

    Parameters
    ----------
    argv : list[str] | None
        Command-line arguments (excluding the program name). When
        ``None``, ``sys.argv[1:]`` is used. Exposed for testability.

    Returns
    -------
    int
        Process exit code. ``0`` on success, non-zero on uncaught error.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    config = load_yaml_config(args.config)

    # CLI flag wins over file config when given.
    if args.headless is not None:
        config.setdefault("behavior", {})["headless"] = args.headless

    filler = FormFiller(
        config=config,
        input_path=args.input,
        output_dir=args.output_dir,
        log_path=args.log_file,
    )
    filler.run(limit=args.limit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
