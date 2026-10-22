"""Convert HEIC images in input/ to PDF in output/. Each image becomes a single-page PDF."""

from pathlib import Path
import pillow_heif

from batch_convert import INPUT_DIR, OUTPUT_DIR
from image_convert import convert_images, save_pdf

# Register HEIF opener with Pillow so it can read .heic files
pillow_heif.register_heif_opener()


def convert_heic_to_pdf(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all HEIC files in the input folder to PDF files in the output folder.

    Note: the image is embedded at 100 DPI with no text layer, so converting the
    resulting PDF onward to Markdown gives poor OCR. Use heic_md.py for that instead.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_images(input_dir, output_dir, ('.heic',), ('.pdf',), save_pdf)


if __name__ == "__main__":
    result = convert_heic_to_pdf()
    if not result.startswith("Converted"):
        print(result)
