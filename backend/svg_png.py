"""Convert SVG images to PNG.

For each .svg in input/, headless Chrome renders it and a transparent-background .png the
same size as the SVG is saved in output/. Images the SVG links to, rather than embeds, are
not loaded.
"""

import os
import tempfile

import fitz  # PyMuPDF
from PIL import Image

import html_svg
from find_files import find_files
from svg_pdf import svg_size, svg_to_pdf

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Folders
input_folder = os.path.join(script_dir, 'input')
output_folder = os.path.join(script_dir, 'output')

# One PNG pixel per CSS pixel, which is the size the SVG says it is.
RENDER_DPI = 96


def convert_svg_to_png() -> str:
    """Convert all SVG files in the input folder to PNG files in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """

    # Create output folder if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    svg_files = find_files(input_folder, '.svg')

    if not svg_files:
        png_present = find_files(input_folder, '.png')
        if png_present:
            return "That file is already in png format"
        return "No SVG files found in input folder"

    if not os.path.exists(html_svg.CHROME_PATH):
        return f"Google Chrome not found at {html_svg.CHROME_PATH}"

    converted = []
    errors = []

    for svg_file in svg_files:
        try:
            filename = os.path.splitext(os.path.basename(svg_file))[0]
            png_file = os.path.join(output_folder, f"{filename}.png")

            existed_before = os.path.exists(png_file)
            print(f"Converting {os.path.basename(svg_file)} to png")

            with tempfile.TemporaryDirectory() as work_dir:
                pdf_file = os.path.join(work_dir, "page.pdf")
                svg_to_pdf(svg_file, pdf_file, work_dir)
                with fitz.open(pdf_file) as document:
                    pixmap = document[0].get_pixmap(dpi=RENDER_DPI, alpha=True)
                    rendered = Image.frombytes(
                        "RGBA", (pixmap.width, pixmap.height), pixmap.samples
                    )

            # Chrome rounds the page size up by a fraction of a pixel, which can leave the
            # render a pixel bigger than the SVG. Pasting it on a canvas of the exact size
            # trims that, and pads with transparency if it ever comes out smaller.
            width, height = (round(side) for side in svg_size(svg_file))
            png = Image.new("RGBA", (width, height))
            png.paste(rendered, (0, 0))
            png.save(png_file)

            print(f"Converted {os.path.basename(svg_file)} to {filename}.png")
            if existed_before:
                print(f"Overwrote existing file: {filename}.png")
            converted.append(f"{filename}.png")

        except Exception as e:
            print(f"Error converting {svg_file}: {str(e)}")
            errors.append(f"{os.path.basename(svg_file)}: {e}")

    if not converted:
        return f"No files converted. {len(errors)} failed: {'; '.join(errors)}"

    summary = f"Converted {len(converted)} file(s) to output/: {', '.join(converted)}"
    if errors:
        summary += f". {len(errors)} failed: {'; '.join(errors)}"
    return summary


if __name__ == "__main__":
    result = convert_svg_to_png()
    if not result.startswith("Converted"):
        print(result)
