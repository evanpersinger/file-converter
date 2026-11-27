"""Convert R Markdown (.Rmd) files to PDF.

For each .Rmd in input/ (or a file passed as an argument), renders it with R's rmarkdown,
which runs the code chunks, to a PDF in output/.
"""


import os
import sys
import argparse
import tempfile
from pathlib import Path
from shutil import which

from batch_convert import read_text
from external_tool import run_tool
from find_files import find_files

# Default folders live next to this script, so `python backend/Rmd_pdf.py` finds
# backend/input regardless of the shell's working directory.
SCRIPT_DIR = Path(__file__).resolve().parent


# convert an R markdown file to a pdf file
def convert_rmd_to_pdf(rmd_path: str, output_path: str | None = None,
                       input_dir: str | None = None, output_dir: str | None = None) -> bool:
    """Convert an R Markdown file to PDF.

    Needs R with the rmarkdown package. A render that fails is reported with R's error.

    Args:
        rmd_path: Path to the .Rmd file (relative to input folder or absolute)
        output_path: Desired output PDF filename. If None, uses input stem + .pdf
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

    # if the provided path already points to a PDF, stop
    if Path(rmd_path).suffix.lower() == ".pdf":
        print("That file is already in pdf format")
        return False

    # Build full input path
    full_input_path = Path(rmd_path) if os.path.isabs(str(rmd_path)) else input_dir / rmd_path
    if not full_input_path.exists():
        print(f"Error: Rmd file '{full_input_path}' not found")
        return False

    # Compute output name
    if output_path is None:
        pdf_name = f"{full_input_path.stem}.pdf"
    else:
        pdf_name = Path(output_path).name
    full_output_path = output_dir / pdf_name
    existed_before = full_output_path.exists()

    if not which("Rscript"):
        print("R not found. Install R, then run: Rscript -e 'install.packages(\"rmarkdown\")'")
        return False

    temp_path = None
    try:
        content = read_text(full_input_path, translate_newlines=True)

        # Check if YAML header exists and add geometry settings for proper margins
        if content.startswith('---'):
            # Find the end of YAML header
            yaml_end = content.find('---', 3)
            if yaml_end != -1:
                yaml_header = content[:yaml_end + 3]
                # Add geometry settings if not already present
                if 'geometry:' not in yaml_header and 'margin' not in yaml_header.lower():
                    yaml_header = yaml_header.replace('\n---', '\ngeometry: margin=1in\n---')
                    content = yaml_header + content[yaml_end + 3:]
        else:
            # No YAML header, prepend one
            content = '---\ngeometry: margin=1in\n---\n\n' + content

        # R renders this copy, so the margins don't change the original file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.Rmd', delete=False, encoding='utf-8') as tmp:
            tmp.write(content)
            temp_path = tmp.name

        r_expr = (
            "rmarkdown::render("
            f"\"{temp_path}\", "
            "output_format=\"pdf_document\", "
            f"output_file=\"{pdf_name}\", "
            f"output_dir=\"{str(output_dir)}\")"
        )
        cmd = [
            "Rscript",
            "-e",
            r_expr,
        ]
        print(f"Converting {full_input_path.name} to pdf")
        result = run_tool(cmd)
        if result.returncode == 0 and full_output_path.exists():
            print(f"Converted {full_input_path.name} to {full_output_path.name}")
            if existed_before:
                print(f"Overwrote existing file: {full_output_path.name}")
            return True
        print(f"rmarkdown failed: {result.stderr.strip() or 'unknown error'}")
        return False
    except Exception as e:
        print(f"rmarkdown failed with error: {e}")
        return False
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


def main():
    parser = argparse.ArgumentParser(description="Convert R Markdown files to PDF")
    parser.add_argument("rmd_file", nargs="?", help="R Markdown file to convert (optional)")
    parser.add_argument("output_file", nargs="?", help="Output PDF filename (optional)")
    parser.add_argument("--input-dir", default=SCRIPT_DIR / "input", help="Input directory (default: backend/input)")
    parser.add_argument("--output-dir", default=SCRIPT_DIR / "output", help="Output directory (default: backend/output)")
    
    args = parser.parse_args()
    
    # Set up directories
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    if args.rmd_file:
        # Convert specific file
        success = convert_rmd_to_pdf(args.rmd_file, args.output_file, input_dir, output_dir)
        if not success:
            sys.exit(1)
    else:
        # convert all .Rmd files in input/
        rmd_files = [Path(p) for p in find_files(input_dir, ".Rmd")]
        if not rmd_files:
            print(f"No .Rmd files found in {input_dir} folder")
            print("Usage: python Rmd_pdf.py <file.Rmd> [output.pdf] [--input-dir DIR] [--output-dir DIR]")
            print("Example: python Rmd_pdf.py report.Rmd")
            print("Example: python Rmd_pdf.py report.Rmd my_report.pdf")
            print("Example: python Rmd_pdf.py --input-dir myinput --output-dir myoutput")
            return
        any_failed = False
        for rmd in rmd_files:
            ok = convert_rmd_to_pdf(rmd.name, None, input_dir, output_dir)
            if not ok:
                any_failed = True
        if any_failed:
            sys.exit(1)


if __name__ == "__main__":
    main()


