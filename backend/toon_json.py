"""Convert TOON files to JSON.

For each .toon in input/, writes a .json file with the same data to output/.
"""

import json
from pathlib import Path

import toon_format

from batch_convert import INPUT_DIR, OUTPUT_DIR, convert_files


# convert a toon file to json text
# handles conversion logic
def toon_to_json(toon_file):
    """Read a TOON file and return the same data as indented JSON text"""
    # utf-8-sig so a file saved with a byte order mark still parses
    with open(toon_file, 'r', encoding='utf-8-sig') as f:
        data = toon_format.loads(f.read())
    return json.dumps(data, indent=2, ensure_ascii=False) + '\n'


def _write_json(source: Path, dest: Path) -> None:
    dest.write_text(toon_to_json(source), encoding='utf-8')


# convert all toon files to json files
# handles file system operations
def convert_toon_to_json(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all TOON files in the input folder to JSON files in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_files(
        input_dir, output_dir, ('.toon',), ('.json',), _write_json, target_label="JSON"
    )


if __name__ == "__main__":
    result = convert_toon_to_json()
    if not result.startswith("Converted"):
        print(result)
