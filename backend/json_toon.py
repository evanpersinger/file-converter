"""Convert JSON files to TOON.

For each .json in input/, writes a .toon file with the same data to output/.
"""

import json
from pathlib import Path

import toon_format

from batch_convert import INPUT_DIR, OUTPUT_DIR, convert_files


def _reject_constant(name: str):
    # Python's json module accepts NaN and Infinity, and TOON would turn them into null.
    raise ValueError(f"{name} is not valid JSON")


# convert a json file to toon text
# handles conversion logic
def json_to_toon(json_file):
    """Read a JSON file and return the same data as TOON text"""
    # utf-8-sig so a file saved with a byte order mark still parses
    with open(json_file, 'r', encoding='utf-8-sig') as f:
        data = json.load(f, parse_constant=_reject_constant)
    return toon_format.dumps(data) + '\n'


def _write_toon(source: Path, dest: Path) -> None:
    dest.write_text(json_to_toon(source), encoding='utf-8')


# convert all json files to toon files
# handles file system operations
def convert_json_to_toon(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all JSON files in the input folder to TOON files in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_files(
        input_dir, output_dir, ('.json',), ('.toon',), _write_toon, target_label="TOON"
    )


if __name__ == "__main__":
    result = convert_json_to_toon()
    if not result.startswith("Converted"):
        print(result)
