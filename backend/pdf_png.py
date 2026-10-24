"""Render each page of the PDFs in input/ to a PNG in output/ (name.png, or name_pageN.png for multi-page)."""

import os
from pathlib import Path
import fitz  # PyMuPDF

from batch_convert import INPUT_DIR, OUTPUT_DIR
from find_files import find_files

# Rendering resolution. PDF pages are vector, so this is a choice rather than a
# property of the file: 600 is the sharpest the converter makes.
RENDER_DPI = 600

# The most pixels one page may render to, so an oversize page (a poster) can't exhaust
# memory. A Letter page at 600 DPI is about 34 million and a tabloid page about 67 million,
# so only larger pages are rendered below RENDER_DPI.
MAX_PAGE_PIXELS = 80_000_000


def _page_dpi(page: fitz.Page) -> int:
    """RENDER_DPI, or lower for a page that would render to more than MAX_PAGE_PIXELS."""
    area_in_square_inches = (page.rect.width / 72) * (page.rect.height / 72)
    return min(RENDER_DPI, int((MAX_PAGE_PIXELS / area_in_square_inches) ** 0.5))


def convert_pdf_to_png(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Render every page of each PDF in the input folder to a PNG in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """

    # Create output folder if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    pdf_files = find_files(input_dir, '.pdf')

    if not pdf_files:
        png_present = find_files(input_dir, '.png')
        if png_present:
            return "That file is already in png format"
        return "No PDF files found in input folder"

    converted = []
    errors = []

    for pdf_file in pdf_files:
        try:
            filename = os.path.splitext(os.path.basename(pdf_file))[0]
            print(f"Converting {os.path.basename(pdf_file)} to png")

            with fitz.open(pdf_file) as document:
                if document.page_count == 0:
                    errors.append(f"{os.path.basename(pdf_file)}: no pages")
                    continue

                page_count = document.page_count
                output_names = []
                overwritten = []
                for index, page in enumerate(document, start=1):
                    # Single-page PDFs keep the plain name, so the common case does
                    # not end up with a pointless "_page1" suffix.
                    suffix = "" if page_count == 1 else f"_page{index}"
                    png_name = f"{filename}{suffix}.png"
                    png_file = os.path.join(output_dir, png_name)
                    if os.path.exists(png_file):
                        overwritten.append(png_name)

                    page.get_pixmap(dpi=_page_dpi(page)).save(png_file)
                    output_names.append(png_name)
                    converted.append(png_name)

                    if page_count > 1:
                        print(f"\rConverting {os.path.basename(pdf_file)}: {index * 100 // page_count}%",
                              end="", flush=True)

                if page_count > 1:
                    print()  # move off the in-place progress line
                    print(f"Converted {os.path.basename(pdf_file)} to output/: {', '.join(output_names)}")
                else:
                    print(f"Converted {os.path.basename(pdf_file)} to {output_names[0]}")

                for name in overwritten:
                    print(f"Overwrote existing file: {name}")

        except Exception as e:
            print(f"Error converting {pdf_file}: {str(e)}")
            errors.append(f"{os.path.basename(pdf_file)}: {e}")

    if not converted:
        return f"No files converted. {len(errors)} failed: {'; '.join(errors)}"

    summary = f"Converted {len(converted)} file(s) to output/: {', '.join(converted)}"
    if errors:
        summary += f". {len(errors)} failed: {'; '.join(errors)}"
    return summary


if __name__ == "__main__":
    result = convert_pdf_to_png()
    if not result.startswith("Converted"):
        print(result)
