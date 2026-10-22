"""Convert PNG images to JPG.

For each .png in input/, opens it with Pillow and saves a .jpg in output/. JPEG has no
transparency, so transparent areas are painted white.
"""

from pathlib import Path

from image_convert import INPUT_DIR, OUTPUT_DIR, convert_images, save_jpg_on_white


def convert_png_to_jpg(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all PNG files in the input folder to JPG files in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_images(input_dir, output_dir, ('.png',), ('.jpg', '.jpeg'), save_jpg_on_white)


if __name__ == "__main__":
    result = convert_png_to_jpg()
    if not result.startswith("Converted"):
        print(result)
