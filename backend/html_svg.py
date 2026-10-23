"""Render HTML files in input/ to vector SVG pages in output/ (name.svg, or name_pageN.svg
for multi-page).

Headless Chrome prints each file to a PDF in a temp folder, then pymupdf turns each PDF
page into an SVG. The pages are Letter size with Chrome's default margins, so a long
HTML file splits across several SVGs. Linked CSS and images are found only if they sit
next to the HTML in input/.
"""

import os
import tempfile
from pathlib import Path

import fitz  # PyMuPDF

from batch_convert import INPUT_DIR, OUTPUT_DIR
from external_tool import run_tool
from find_files import find_files

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# Text becomes outlines, so the SVG looks the same on a machine without the page's fonts,
# at the cost of text that cannot be selected or edited. False keeps real <text> elements:
# about an eighth the size on a small test page, but they fall back to whatever fonts the
# viewer has.
TEXT_AS_PATH = True


def _print_to_pdf(html_file: str, pdf_file: str, profile_dir: str) -> None:
    """Print one HTML file to a PDF with headless Chrome.

    The throwaway profile keeps Chrome from handing the job to a Chrome that is already
    open. Chrome writes a lot of harmless errors to stderr, so only the exit code and the
    PDF are checked.

    Raises:
        RuntimeError: If Chrome times out, fails, or writes no PDF.
    """
    command = [
        CHROME_PATH,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--user-data-dir={profile_dir}",
        f"--print-to-pdf={pdf_file}",
        Path(html_file).resolve().as_uri(),
    ]
    result = run_tool(command)

    if result.returncode != 0 or not os.path.exists(pdf_file):
        raise RuntimeError(f"Chrome exited with code {result.returncode} and wrote no PDF")


def _write_pages(pdf_file: str, filename: str, output_dir: str | Path) -> list[str]:
    """Write each page of the PDF to an SVG in the output folder.

    Returns:
        The names of the SVG files written.
    """
    names = []
    with fitz.open(pdf_file) as document:
        page_count = document.page_count
        for index, page in enumerate(document, start=1):
            # Single-page files keep the plain name, so the common case does not end up
            # with a pointless "_page1" suffix.
            suffix = "" if page_count == 1 else f"_page{index}"
            svg_name = f"{filename}{suffix}.svg"
            svg_file = os.path.join(output_dir, svg_name)
            if os.path.exists(svg_file):
                print(f"Overwrote existing file: {svg_name}")

            svg = page.get_svg_image(text_as_path=TEXT_AS_PATH)
            with open(svg_file, 'w', encoding='utf-8') as f:
                f.write(svg)
            names.append(svg_name)
    return names


def convert_html_to_svg(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all HTML files in the input folder to SVG files in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """

    # Create output folder if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    html_files = find_files(input_dir, '.html', '.htm')

    if not html_files:
        svg_present = find_files(input_dir, '.svg')
        if svg_present:
            return "That file is already in svg format"
        return "No HTML files found in input folder"

    if not os.path.exists(CHROME_PATH):
        return f"Google Chrome not found at {CHROME_PATH}"

    converted = []
    errors = []

    for html_file in html_files:
        try:
            filename = os.path.splitext(os.path.basename(html_file))[0]
            print(f"Converting {os.path.basename(html_file)} to svg")

            with tempfile.TemporaryDirectory() as work_dir:
                pdf_file = os.path.join(work_dir, "page.pdf")
                _print_to_pdf(html_file, pdf_file, os.path.join(work_dir, "profile"))
                names = _write_pages(pdf_file, filename, output_dir)

            print(f"Converted {os.path.basename(html_file)} to {', '.join(names)}")
            converted.extend(names)

        except Exception as e:
            print(f"Error converting {html_file}: {str(e)}")
            errors.append(f"{os.path.basename(html_file)}: {e}")

    if not converted:
        return f"No files converted. {len(errors)} failed: {'; '.join(errors)}"

    summary = f"Converted {len(converted)} file(s) to output/: {', '.join(converted)}"
    if errors:
        summary += f". {len(errors)} failed: {'; '.join(errors)}"
    return summary


if __name__ == "__main__":
    result = convert_html_to_svg()
    if not result.startswith("Converted"):
        print(result)
