"""Manual integration check against the live DemoQA practice form.

This script is NOT a pytest test. It exists so you can WATCH the bot
drive a real Chrome window after changes to driver / waits / fields,
and confirm that everything composes end-to-end.

What it does:

1. Loads ``config.yaml`` (URL, selectors, field-type map).
2. Loads ``data/sample_input.xlsx`` and validates its columns.
3. Builds the Chrome WebDriver (anti-detection enabled).
4. Navigates to the target URL.
5. Fills every field of the FIRST row by dispatching through
   ``fill_field`` -- text, radio, dropdown, and so on.
6. Pauses so you can inspect the page before closing.

The script never submits the form. Submission is a separate concern
that will live in ``form_filler.py`` once the whole pipeline is wired.

Run from the project root with the venv active::

    python scripts/manual_demo.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# This script lives in scripts/, but imports automation_core/ which is
# one directory up. Add the project root to sys.path so the imports
# below resolve regardless of where Python is invoked from.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402  -- import after sys.path adjustment is intentional

from automation_core.driver import build_driver  # noqa: E402
from automation_core.fields import fill_field  # noqa: E402
from automation_core.io_utils import load_spreadsheet, validate_columns  # noqa: E402


CONFIG_PATH = ROOT / "config.yaml"
INPUT_PATH = ROOT / "data" / "sample_input.xlsx"


def main() -> None:
    # ---- 1. Load configuration ------------------------------------------
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    target_url = config["target"]["url"]
    field_specs = config["fields"]
    expected_columns = list(field_specs.keys())

    # ---- 2. Load and validate spreadsheet -------------------------------
    df = load_spreadsheet(INPUT_PATH)
    validate_columns(df, expected_columns)

    print(f"Loaded {len(df)} row(s) from {INPUT_PATH.name}.")
    first_row = df.iloc[0].to_dict()
    print(f"Will fill the first row: {first_row}")

    # ---- 3. Open the browser --------------------------------------------
    driver = build_driver(headless=False)

    try:
        # ---- 4. Navigate to the target page ----------------------------
        print(f"\nNavigating to {target_url}")
        driver.get(target_url)

        # ---- 5. Fill each declared field -------------------------------
        for column_name, field_spec in field_specs.items():
            value = first_row[column_name]
            field_type = field_spec["type"]
            selector = field_spec["selector"]

            print(f"  - {column_name} ({field_type}): {value!r}")
            fill_field(driver, field_type, selector, value)

        # ---- 6. Pause for visual inspection ----------------------------
        print("\nForm filled. Inspect the page in the browser window.")
        input("Press Enter here to close the browser...")
    finally:
        driver.quit()
        print("Browser closed.")


if __name__ == "__main__":
    main()
