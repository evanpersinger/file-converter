"""Convert Excel workbooks to CSV.

For each .xlsx in input/, reads it with pandas and writes a .csv to output/.
"""

import pandas as pd
import os
import re
from pathlib import Path

from batch_convert import INPUT_DIR, OUTPUT_DIR
from find_files import find_files


def _safe_name(sheet_name: str) -> str:
    """Make a sheet name usable as part of a filename.

    Excel allows spaces and punctuation in a tab name, including characters that would
    either break the path or escape the output folder entirely.
    """
    cleaned = re.sub(r'[<>:"/\\|?*]', "_", sheet_name).strip().strip(".")
    return cleaned or "sheet"


# pandas stringifies a date-only cell as "2024-01-05 00:00:00" under dtype=str.
_MIDNIGHT = r" 00:00:00(?:\.0+)?$"


def _trim_midnight(sheets: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Show date-only cells as YYYY-MM-DD instead of with a 00:00:00 time part."""
    return {
        name: df.replace(to_replace=r"^(\d{4}-\d{2}-\d{2})" + _MIDNIGHT, value=r"\1", regex=True)
        for name, df in sheets.items()
    }


def convert_xlsx_to_csv(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all XLSX files in the input folder to CSV files in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    # Create output folder if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Find all .xlsx files in the folder
    excel_files = find_files(input_dir, '.xlsx')

    if not excel_files:
        # If only CSVs are present, notify they're already CSV
        csv_present = find_files(input_dir, '.csv')
        if csv_present:
            return "That file is already in csv format"
        return "No Excel files found in input folder"

    converted = []
    errors = []

    for file in excel_files:
        # Get just the filename (outside the try so it's always available for errors)
        filename = os.path.basename(file)

        try:
            stem = os.path.splitext(filename)[0]
            print(f"Converting {filename} to csv")

            # sheet_name=None reads every sheet, not just the first. A workbook is a
            # stack of separate grids and a CSV is one grid, so a multi-sheet workbook
            # has to become several files. Reading only the first sheet, which is what
            # pandas does by default, converts a three-tab workbook into one CSV and
            # says nothing about the two tabs it dropped.
            #
            # dtype=str keeps the cell types the workbook already declares. Without it
            # pandas re-guesses them, and a cell explicitly stored as text comes back
            # as something else: '007' as the number 7, 'TRUE' as the word True. There
            # is nothing to lose by reading as text here, since the output is a CSV and
            # a CSV carries no types either way.
            sheets = _trim_midnight(pd.read_excel(file, sheet_name=None, dtype=str))

            for sheet_name, df in sheets.items():
                # A single-sheet workbook keeps the plain name. Naming it after the
                # sheet would rename the common case to serve the rare one.
                if len(sheets) == 1:
                    csv_filename = f"{stem}.csv"
                else:
                    csv_filename = f"{stem}_{_safe_name(sheet_name)}.csv"

                csv_path = os.path.join(output_dir, csv_filename)
                existed_before = os.path.exists(csv_path)
                df.to_csv(csv_path, index=False)
                print(f"Converted {filename} [{sheet_name}] to {csv_filename}")
                if existed_before:
                    print(f"Overwrote existing file: {csv_filename}")
                converted.append(csv_filename)

        except Exception as e:
            print(f"Error converting {filename}: {e}")
            errors.append(f"{filename}: {e}")

    if not converted:
        return f"No files converted. {len(errors)} failed: {'; '.join(errors)}"

    summary = f"Converted {len(converted)} file(s) to output/: {', '.join(converted)}"
    if errors:
        summary += f". {len(errors)} failed: {'; '.join(errors)}"
    return summary


if __name__ == "__main__":
    result = convert_xlsx_to_csv()
    if not result.startswith("Converted"):
        print(result)
