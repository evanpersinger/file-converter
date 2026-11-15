"""Convert JPG images in input/ to Markdown in output/ via Tesseract OCR.

English only (lang='eng'): other languages come back as garbled English, not an error.
"""

from pathlib import Path

from batch_convert import INPUT_DIR, OUTPUT_DIR
from image_convert import convert_images
from image_md import ocr_to_markdown


def convert_jpg_to_markdown(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all JPG files in the input folder to Markdown files in the output folder.

    Uses OCR, so this reads text straight out of the image.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_images(
        input_dir, output_dir, ('.jpg', '.jpeg'), ('.md',), ocr_to_markdown,
        target_label="markdown",
    )


if __name__ == "__main__":
    result = convert_jpg_to_markdown()
    if not result.startswith("Converted"):
        print(result)
