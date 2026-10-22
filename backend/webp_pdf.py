"""Convert WebP images to PDF.

For each .webp in input/, opens it with Pillow and saves a PDF in output/ with one page
per frame, so a static WebP gives a single page. Each frame is flattened onto white.
"""

from pathlib import Path

from batch_convert import INPUT_DIR, OUTPUT_DIR
from image_convert import convert_images, save_pdf_pages


def convert_webp_to_pdf(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all WebP files in the input folder to PDF files in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_images(input_dir, output_dir, ('.webp',), ('.pdf',), save_pdf_pages)


if __name__ == "__main__":
    result = convert_webp_to_pdf()
    if not result.startswith("Converted"):
        print(result)
