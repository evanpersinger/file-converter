"""Convert PNG images to PDF.

For each .png in input/, opens it with Pillow, flattens to RGB (dropping any
transparency), and saves it as a single-page PDF in output/.
"""

from pathlib import Path

from image_convert import INPUT_DIR, OUTPUT_DIR, convert_images, save_pdf


def convert_png_to_pdf(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all PNG files in the input folder to PDF files in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_images(input_dir, output_dir, ('.png',), ('.pdf',), save_pdf)


if __name__ == "__main__":
    result = convert_png_to_pdf()
    if not result.startswith("Converted"):
        print(result)
