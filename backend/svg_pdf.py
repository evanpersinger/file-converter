"""Convert SVG images to PDF.

For each .svg in input/, headless Chrome prints a one-page PDF in output/ the same size as
the SVG. Images the SVG links to, rather than embeds, are not loaded.
"""

import os
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import html_svg
from batch_convert import INPUT_DIR, OUTPUT_DIR, convert_files

# CSS pixels per SVG length unit, at the 96 pixels per inch browsers use.
PX_PER_UNIT = {
    "": 1, "px": 1, "pt": 96 / 72, "pc": 16, "mm": 96 / 25.4, "cm": 96 / 2.54, "in": 96,
}
LENGTH = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*(px|pt|pc|mm|cm|in)?\s*$")

# Chrome prints a bare SVG onto a Letter page and clips what does not fit, so the SVG goes
# in a page whose size is its own.
WRAPPER = """<!doctype html><html><head><meta charset="utf-8"><style>
@page {{ size: {width:.2f}px {height:.2f}px; margin: 0 }}
html, body {{ margin: 0; padding: 0; overflow: hidden }}
img {{ display: block; width: {width:.2f}px; height: {height:.2f}px }}
</style></head><body><img src="{src}"></body></html>
"""


def _length_px(value: str | None) -> float | None:
    """Return an SVG length in CSS pixels, or None for a missing or relative one like 100%."""
    match = LENGTH.match(value or "")
    if not match:
        return None
    return float(match.group(1)) * PX_PER_UNIT[match.group(2) or ""]


def svg_size(svg_file: str) -> tuple[float, float]:
    """Return the SVG's width and height in CSS pixels.

    Uses the width and height attributes, and falls back to the viewBox when either is
    missing or relative.

    Raises:
        ValueError: If neither gives a size.
    """
    root = ET.parse(svg_file).getroot()

    width, height = _length_px(root.get("width")), _length_px(root.get("height"))
    if width and height:
        return width, height

    view_box = root.get("viewBox", "").replace(",", " ").split()
    if len(view_box) == 4:
        try:
            width, height = float(view_box[2]), float(view_box[3])
        except ValueError:
            pass
        else:
            if width > 0 and height > 0:
                return width, height

    raise ValueError("the SVG has no width and height or viewBox, so its size is unknown")


def svg_to_pdf(svg_file: str, pdf_file: str, work_dir: str) -> None:
    """Print one SVG to a one-page PDF the size of the SVG with headless Chrome.

    work_dir holds the wrapper page, a copy of the SVG next to it (Chrome loads the page over
    http, which can't reach a file:// path) and Chrome's throwaway profile.

    Raises:
        ValueError: If the SVG's size is unknown.
        RuntimeError: If Chrome times out, fails, or writes no PDF.
    """
    width, height = svg_size(svg_file)

    shutil.copyfile(svg_file, os.path.join(work_dir, "source.svg"))
    wrapper_file = os.path.join(work_dir, "wrapper.html")
    with open(wrapper_file, 'w', encoding='utf-8') as f:
        f.write(WRAPPER.format(width=width, height=height, src="source.svg"))

    html_svg._print_to_pdf(wrapper_file, pdf_file, os.path.join(work_dir, "profile"))


def chrome_missing() -> str | None:
    """The message to return when Chrome isn't installed, or None when it is."""
    if not os.path.exists(html_svg.CHROME_PATH):
        return f"Google Chrome not found at {html_svg.CHROME_PATH}"
    return None


def _print_pdf(source: Path, dest: Path) -> None:
    # Printed to a temp folder first, so a stale PDF from an earlier run cannot
    # make a failed Chrome run look like it worked.
    with tempfile.TemporaryDirectory() as work_dir:
        printed_file = os.path.join(work_dir, "page.pdf")
        svg_to_pdf(str(source), printed_file, work_dir)
        shutil.copyfile(printed_file, dest)


def convert_svg_to_pdf(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all SVG files in the input folder to PDF files in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_files(
        input_dir, output_dir, ('.svg',), ('.pdf',), _print_pdf, precheck=chrome_missing
    )


if __name__ == "__main__":
    result = convert_svg_to_pdf()
    if not result.startswith("Converted"):
        print(result)
