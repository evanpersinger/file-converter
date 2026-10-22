"""Convert WebP images to PNG.

For each .webp in input/, opens it with Pillow and saves a .png in output/. Transparency
is kept, and animated WebPs give their first frame.
"""

from pathlib import Path

from batch_convert import INPUT_DIR, OUTPUT_DIR
from image_convert import convert_images, saver


def convert_webp_to_png(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all WebP files in the input folder to PNG files in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_images(input_dir, output_dir, ('.webp',), ('.png',), saver('PNG'))


if __name__ == "__main__":
    result = convert_webp_to_png()
    if not result.startswith("Converted"):
        print(result)
