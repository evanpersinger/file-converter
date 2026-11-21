"""Render each page of the PDFs in input/ to a JPG in output/ (name.jpg, or name_pageN.jpg for multi-page)."""

from pathlib import Path

from batch_convert import INPUT_DIR, OUTPUT_DIR
from pdf_png import render_pdf_pages

# JPG is lossy and a 600 DPI page is huge as one, so this renders lower than pdf_png does.
RENDER_DPI = 300


def convert_pdf_to_jpg(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Render every page of each PDF in the input folder to a JPG in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return render_pdf_pages(input_dir, output_dir, "jpg", RENDER_DPI)


if __name__ == "__main__":
    result = convert_pdf_to_jpg()
    if not result.startswith("Converted"):
        print(result)
