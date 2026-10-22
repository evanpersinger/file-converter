"""Convert CSV files to Excel workbooks.

For each .csv in input/, reads it with pandas and writes an .xlsx to output/.
"""

import pandas as pd
from pathlib import Path

from batch_convert import INPUT_DIR, OUTPUT_DIR, convert_files


def _round_trips(converted: pd.Series, original: pd.Series) -> bool:
    """Would printing the converted column back out give the original characters?"""
    filled = original.notna()
    return bool((converted[filled].map(str) == original[filled]).all())


def _infer_lossless(column: pd.Series) -> pd.Series:
    """Give a column its real type back, but only when nothing is lost by doing so.

    A CSV holds characters, not types, so pandas has to guess. Guessing per column is
    usually right and occasionally destructive: '007' is a product code, not the number
    seven, and 'TRUE' is a word before it is a boolean. Reading everything as text and
    handing it all to Excel as text avoids that but costs you a price column Excel can
    add up, so each column is converted only if printing it back gives exactly the
    characters that came in.
    """
    try:
        numeric = pd.to_numeric(column)
    except (ValueError, TypeError):
        return column

    # Nullable integer first. A single blank cell forces plain to_numeric to float,
    # which would write 1 as 1.0.
    try:
        as_int = numeric.astype("Int64")
    except (ValueError, TypeError):
        as_int = None

    for candidate in (as_int, numeric):
        if candidate is not None and _round_trips(candidate, column):
            return candidate
    return column


def _write_workbook(source: Path, dest: Path) -> None:
    # Read as text so pandas' own guessing can't damage anything, then put back
    # only the types that survive being printed out again.
    df = pd.read_csv(source, dtype=str).apply(_infer_lossless)

    # xlsxwriter rather than the default openpyxl. openpyxl stores any string
    # starting with '=' as a live formula, which both loses the original text
    # and hands the user a workbook their spreadsheet will execute on open.
    with pd.ExcelWriter(
        dest,
        engine="xlsxwriter",
        engine_kwargs={"options": {"strings_to_formulas": False}},
    ) as writer:
        df.to_excel(writer, index=False)


def convert_csv_to_xlsx(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all CSV files in the input folder to XLSX files in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_files(
        input_dir, output_dir, ('.csv',), ('.xlsx',), _write_workbook, target_label="Excel"
    )


if __name__ == "__main__":
    result = convert_csv_to_xlsx()
    if not result.startswith("Converted"):
        print(result)
