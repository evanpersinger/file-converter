"""Convert JPG/JPEG images to PNG.

For each .jpg/.jpeg in input/, opens it with Pillow and saves it as a .png in
output/. JPEG carries no transparency, so nothing is lost on the way across.
"""

from pathlib import Path

from image_convert import INPUT_DIR, OUTPUT_DIR, convert_images, saver


def convert_jpg_to_png(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all JPG/JPEG files in the input folder to PNG files in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_images(input_dir, output_dir, ('.jpg', '.jpeg'), ('.png',), saver('PNG'))


if __name__ == "__main__":
    result = convert_jpg_to_png()
    if not result.startswith("Converted"):
        print(result)
