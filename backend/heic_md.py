"""Convert HEIC images in input/ to Markdown in output/ via Tesseract OCR.

English only (lang='eng'): other languages come back as garbled English, not an error.
"""

from pathlib import Path
import pillow_heif

from batch_convert import INPUT_DIR, OUTPUT_DIR
from image_convert import convert_images
from image_md import ocr_to_markdown

pillow_heif.register_heif_opener()


def convert_heic_to_markdown(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all HEIC files in the input folder to Markdown files in the output folder.

    Uses OCR and processes the HEIC in memory, so no intermediate JPG is written.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_images(
        input_dir, output_dir, ('.heic',), ('.md',), ocr_to_markdown, target_label="markdown"
    )


if __name__ == "__main__":
    result = convert_heic_to_markdown()
    if not result.startswith("Converted"):
        print(result)
