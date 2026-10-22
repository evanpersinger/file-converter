"""Convert HEIC images to JPG.

Registers the HEIF opener with Pillow, then for each .heic in input/ opens it,
converts to RGB, and saves a .jpg to output/.
"""

from pathlib import Path
from PIL import Image
import pillow_heif

from batch_convert import INPUT_DIR, OUTPUT_DIR
from image_convert import convert_images

# Register HEIF opener with Pillow so it can read .heic files
pillow_heif.register_heif_opener()


def _save_jpg(img: Image.Image, dest: Path) -> None:
    if img.mode != 'RGB':
        img = img.convert('RGB')
    img.save(dest, 'JPEG', quality=95)


def convert_heic_to_jpg(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all HEIC files in the input folder to JPG files in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_images(input_dir, output_dir, ('.heic',), ('.jpg', '.jpeg'), _save_jpg)


if __name__ == "__main__":
    result = convert_heic_to_jpg()
    if not result.startswith("Converted"):
        print(result)
