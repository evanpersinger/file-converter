"""Convert JPG/JPEG images to PDF.

For each image in input/, opens it with Pillow, converts to RGB, and saves it as a
single-page PDF in output/.
"""

from pathlib import Path

from batch_convert import INPUT_DIR, OUTPUT_DIR
from image_convert import convert_images, save_pdf


def convert_jpg_to_pdf(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all JPG files in the input folder to PDF files in the output folder.

    Note: the image is embedded at 100 DPI with no text layer, so converting the
    resulting PDF onward to Markdown gives poor OCR. Use jpg_md.py for that instead.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_images(input_dir, output_dir, ('.jpg', '.jpeg'), ('.pdf',), save_pdf)


if __name__ == "__main__":
    result = convert_jpg_to_pdf()
    if not result.startswith("Converted"):
        print(result)
