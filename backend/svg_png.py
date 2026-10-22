"""Convert SVG images to PNG.

For each .svg in input/, headless Chrome renders it and a transparent-background .png the
same size as the SVG is saved in output/. Images the SVG links to, rather than embeds, are
not loaded.
"""

import os
import tempfile

import fitz  # PyMuPDF
from PIL import Image

from pathlib import Path

from batch_convert import INPUT_DIR, OUTPUT_DIR, convert_files
from svg_pdf import chrome_missing, svg_size, svg_to_pdf

# One PNG pixel per CSS pixel, which is the size the SVG says it is.
RENDER_DPI = 96


def _render_png(source: Path, dest: Path) -> None:
    with tempfile.TemporaryDirectory() as work_dir:
        pdf_file = os.path.join(work_dir, "page.pdf")
        svg_to_pdf(str(source), pdf_file, work_dir)
        with fitz.open(pdf_file) as document:
            pixmap = document[0].get_pixmap(dpi=RENDER_DPI, alpha=True)
            rendered = Image.frombytes("RGBA", (pixmap.width, pixmap.height), pixmap.samples)

    # Chrome rounds the page size up by a fraction of a pixel, which can leave the
    # render a pixel bigger than the SVG. Pasting it on a canvas of the exact size
    # trims that, and pads with transparency if it ever comes out smaller.
    width, height = (round(side) for side in svg_size(str(source)))
    png = Image.new("RGBA", (width, height))
    png.paste(rendered, (0, 0))
    png.save(dest)


def convert_svg_to_png(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all SVG files in the input folder to PNG files in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_files(
        input_dir, output_dir, ('.svg',), ('.png',), _render_png, precheck=chrome_missing
    )


if __name__ == "__main__":
    result = convert_svg_to_png()
    if not result.startswith("Converted"):
        print(result)
