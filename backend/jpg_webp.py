"""Convert JPG/JPEG images to WebP.

For each .jpg/.jpeg in input/, opens it with Pillow and saves a .webp in output/ at
quality 95.
"""

from pathlib import Path

from image_convert import INPUT_DIR, OUTPUT_DIR, convert_images, saver


def convert_jpg_to_webp(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all JPG/JPEG files in the input folder to WebP files in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_images(
        input_dir, output_dir, ('.jpg', '.jpeg'), ('.webp',), saver('WEBP', quality=95)
    )


if __name__ == "__main__":
    result = convert_jpg_to_webp()
    if not result.startswith("Converted"):
        print(result)
