"""Convert PNG images to WebP.

For each .png in input/, opens it with Pillow and saves a lossless .webp in output/, so no
pixels change. Transparency is kept.
"""

from pathlib import Path

from batch_convert import INPUT_DIR, OUTPUT_DIR
from image_convert import convert_images, saver


def convert_png_to_webp(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all PNG files in the input folder to WebP files in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_images(
        input_dir, output_dir, ('.png',), ('.webp',), saver('WEBP', lossless=True)
    )


if __name__ == "__main__":
    result = convert_png_to_webp()
    if not result.startswith("Converted"):
        print(result)
