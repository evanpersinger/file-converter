"""Convert R scripts (.R) to R Markdown (.Rmd).

For each .R file in input/, puts the script, unchanged, in one R code chunk under a title
header and writes the .Rmd to output/.
"""

import argparse
import os
import sys
from pathlib import Path

from batch_convert import read_text
from find_files import find_files

# Default folders live next to this script, so `python backend/R_Rmd.py` finds
# backend/input regardless of the shell's working directory.
SCRIPT_DIR = Path(__file__).resolve().parent


def convert_r_to_rmd(r_path: str, output_path: str | None = None,
                     input_dir: str | None = None, output_dir: str | None = None) -> bool:
    """Convert an R script to an R Markdown document.

    Args:
        r_path: Path to the .R file (relative to input folder or absolute)
        output_path: Desired output Rmd filename. If None, uses input stem + .Rmd
        input_dir: Input directory (default: the script's input/ folder)
        output_dir: Output directory (default: the script's output/ folder)

    Returns:
        bool: True if conversion successful, False otherwise
    """

    # Set default directories if not provided. Default relative to this script, not
    # the caller's working directory, so it works no matter where it's invoked from.
    script_dir = Path(__file__).resolve().parent

    if input_dir is None:
        input_dir = script_dir / "input"
    else:
        input_dir = Path(input_dir)

    if output_dir is None:
        output_dir = script_dir / "output"
    else:
        output_dir = Path(output_dir)
    
    output_dir.mkdir(exist_ok=True)
    
    # Check if already Rmd format
    if Path(r_path).suffix.lower() == ".rmd":
        print("That file is already in Rmd format")
        return False
    
    # Build full input path
    full_input_path = Path(r_path) if os.path.isabs(str(r_path)) else input_dir / r_path
    if not full_input_path.exists():
        print(f"Error: R file '{full_input_path}' not found")
        return False
    
    # Compute output name
    if output_path is None:
        rmd_name = f"{full_input_path.stem}.Rmd"
    else:
        rmd_name = Path(output_path).name
        if not rmd_name.lower().endswith('.rmd'):
            rmd_name += '.Rmd'
    full_output_path = output_dir / rmd_name
    
    try:
        code = read_text(full_input_path, translate_newlines=True).rstrip("\n")

        existed_before = full_output_path.exists()
        print(f"Converting {full_input_path.name} to Rmd")
        full_output_path.write_text(
            '---\ntitle: "R Analysis"\noutput: pdf_document\n---\n\n'
            f"```{{r}}\n{code}\n```\n",
            encoding="utf-8",
        )

        print(f"Converted {full_input_path.name} to {full_output_path.name}")
        if existed_before:
            print(f"Overwrote existing file: {full_output_path.name}")
        return True

    except Exception as e:
        print(f"Error converting R to Rmd: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Convert R files to R Markdown")
    parser.add_argument("r_file", nargs="?", help="R file to convert (optional)")
    parser.add_argument("output_file", nargs="?", help="Output Rmd filename (optional)")
    parser.add_argument("--input-dir", default=SCRIPT_DIR / "input", help="Input directory (default: backend/input)")
    parser.add_argument("--output-dir", default=SCRIPT_DIR / "output", help="Output directory (default: backend/output)")

    args = parser.parse_args()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    if args.r_file:
        # Convert specific file
        success = convert_r_to_rmd(args.r_file, args.output_file, input_dir, output_dir)
        if not success:
            sys.exit(1)
    else:
        # Convert all .R files in input/
        r_files = [Path(p) for p in find_files(input_dir, ".R")]
        if not r_files:
            print(f"No .R files found in {input_dir} folder")
            print("Usage: python R_Rmd.py <file.R> [output.Rmd] [--input-dir DIR] [--output-dir DIR]")
            print("Example: python R_Rmd.py script.R")
            print("Example: python R_Rmd.py script.R output.Rmd")
            return
        any_failed = False
        for r_file in r_files:
            ok = convert_r_to_rmd(r_file.name, None, input_dir, output_dir)
            if not ok:
                any_failed = True
        if any_failed:
            sys.exit(1)


if __name__ == "__main__":
    main()

