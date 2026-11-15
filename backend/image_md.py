"""Convert PNG, GIF, BMP, TIFF and WebP images in input/ to Markdown in output/ via Tesseract OCR.

English only (lang='eng'): other languages come back as garbled English, not an error.
"""

from pathlib import Path
from PIL import Image

from batch_convert import INPUT_DIR, OUTPUT_DIR
from image_convert import convert_images
from jpg_md import clean_text
from ocr_variants import best_ocr_text

SOURCE_EXTS = ('.png', '.gif', '.bmp', '.tiff', '.webp')


def _ocr_to_markdown(img: Image.Image, dest: Path) -> None:
    # Reads a few preprocessed versions and keeps the most confident (see ocr_variants)
    text = best_ocr_text(img)
    dest.write_text(clean_text(text), encoding='utf-8')


def convert_image_to_markdown(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all PNG, GIF, BMP, TIFF and WebP files in the input folder to Markdown files.

    Uses OCR, so this reads text straight out of the image. A GIF or TIFF with several
    frames or pages has only its first one read.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_images(
        input_dir, output_dir, SOURCE_EXTS, ('.md',), _ocr_to_markdown, target_label="markdown"
    )


if __name__ == "__main__":
    result = convert_image_to_markdown()
    if not result.startswith("Converted"):
        print(result)
