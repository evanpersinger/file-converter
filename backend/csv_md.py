"""Convert CSV files to Markdown tables.

For each .csv in input/, reads the rows, treats the first row as the header, and
writes a pipe-delimited Markdown table to output/.
"""

import csv
from pathlib import Path

from batch_convert import INPUT_DIR, OUTPUT_DIR, convert_files


# convert a csv file to a markdown table
# handles conversion logic
def csv_to_markdown(csv_file):
    """Read a CSV file and return a markdown table string"""
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows: # if csv file is empty, return an empty string
        return ""

    headers = rows[0] # assign first row as headers
    separator = ['---'] * len(headers) # builds separator row
    data_rows = rows[1:] # assign remaining rows as data rows instead of headers

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
