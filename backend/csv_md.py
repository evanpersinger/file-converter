"""Convert CSV files to Markdown tables.

For each .csv in input/, reads the rows, treats the first row as the header, and
writes a pipe-delimited Markdown table to output/.
"""

import csv
from pathlib import Path

from batch_convert import INPUT_DIR, OUTPUT_DIR, convert_files


def _cell(value):
    """Make one cell safe for a markdown table row: a pipe would add a column and a
    newline would end the row."""
    return value.replace('|', '\\|').replace('\r\n', '<br>').replace('\n', '<br>').replace('\r', '<br>')


# convert a csv file to a markdown table
# handles conversion logic
def csv_to_markdown(csv_file):
    """Read a CSV file and return a markdown table string"""
    with open(csv_file, 'r', encoding='utf-8-sig', newline='') as f:  # utf-8-sig drops the BOM Excel adds
        reader = csv.reader(f)
        rows = list(reader)

    if not rows: # if csv file is empty, return an empty string
        return ""

    width = len(rows[0])
    headers = [_cell(c) for c in rows[0]] # assign first row as headers
    separator = ['---'] * width # builds separator row
    # remaining rows are data; short rows are padded so the table stays rectangular
    data_rows = [[_cell(c) for c in row] + [''] * (width - len(row)) for row in rows[1:]]

    # builds markdown table
    lines = []
    lines.append('| ' + ' | '.join(headers) + ' |')
    lines.append('| ' + ' | '.join(separator) + ' |')
    for row in data_rows:
        lines.append('| ' + ' | '.join(row) + ' |')

    return '\n'.join(lines) + '\n' # joins all lines together


def _write_markdown(source: Path, dest: Path) -> None:
    dest.write_text(csv_to_markdown(source), encoding='utf-8')


# convert all csv files to markdown files
# handles file system operations
def convert_csv_to_markdown(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all CSV files in the input folder to Markdown tables in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_files(
        input_dir, output_dir, ('.csv',), ('.md',), _write_markdown, target_label="markdown"
    )


if __name__ == "__main__":
    result = convert_csv_to_markdown()
    if not result.startswith("Converted"):
        print(result)
