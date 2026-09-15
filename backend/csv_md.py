"""Convert CSV files to Markdown tables.

For each .csv in input/, reads the rows, treats the first row as the header, and
writes a pipe-delimited Markdown table to output/.
"""

import csv
import glob
import os

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Folders
input_folder = os.path.join(script_dir, 'input')
output_folder = os.path.join(script_dir, 'output')


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


# convert all csv files to markdown files
# handles file system operations
def convert_csv_to_markdown() -> str:
    """Convert all CSV files in the input folder to Markdown tables in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """

    os.makedirs(output_folder, exist_ok=True)

    csv_files = glob.glob(os.path.join(input_folder, '*.csv'))

    if not csv_files:
        md_present = glob.glob(os.path.join(input_folder, '*.md'))
        if md_present:
            return "File is already in markdown format"
        return "No CSV files found in input folder"

    converted = []
    errors = []

    # loop through all csv files
    for csv_file in csv_files:
        try:
            filename = os.path.splitext(os.path.basename(csv_file))[0] # builds new filename
            md_file = os.path.join(output_folder, f"{filename}.md")

            print(f"Converting {os.path.basename(csv_file)} to md")

            markdown_content = csv_to_markdown(csv_file)

            existed_before = os.path.exists(md_file)
            with open(md_file, 'w', encoding='utf-8') as f:
                f.write(markdown_content)

            print(f"Converted {os.path.basename(csv_file)} to {filename}.md")
            if existed_before:
                print(f"Overwrote existing file: {filename}.md")
            converted.append(f"{filename}.md")

        except Exception as e:
            print(f"Error converting {os.path.basename(csv_file)}: {str(e)}")
            errors.append(f"{os.path.basename(csv_file)}: {e}")

    if not converted:
        return f"No files converted. {len(errors)} failed: {'; '.join(errors)}"

    summary = f"Converted {len(converted)} file(s) to output/: {', '.join(converted)}"
    if errors:
        summary += f". {len(errors)} failed: {'; '.join(errors)}"
    return summary


if __name__ == "__main__":
    result = convert_csv_to_markdown()
    if not result.startswith("Converted"):
        print(result)
