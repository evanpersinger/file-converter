"""Convert HEIC images in input/ to PNG in output/. Keeps the alpha channel, unlike the JPG route."""

from pathlib import Path
from PIL import Image
import pillow_heif

from image_convert import INPUT_DIR, OUTPUT_DIR, convert_images

# Register HEIF opener with Pillow so it can read .heic files
pillow_heif.register_heif_opener()


def _save_png(img: Image.Image, dest: Path) -> None:
    # PNG cannot store CMYK or the paletted-with-alpha oddities some
    # HEIC encoders produce, so anything unusual is normalised first.
    if img.mode not in ('RGB', 'RGBA', 'L', 'LA'):
        img = img.convert('RGBA')
    img.save(dest, 'PNG')


def convert_heic_to_png(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all HEIC files in the input folder to PNG files in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_images(input_dir, output_dir, ('.heic',), ('.png',), _save_png)


if __name__ == "__main__":
    result = convert_heic_to_png()
    if not result.startswith("Converted"):
        print(result)
