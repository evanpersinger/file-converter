"""Trace WebP images in input/ into vector SVG paths in output/ with vtracer.

WebP is often lossy, which traces as noise, so prefer a PNG source when you have one.
Pillow decodes the file and vtracer is handed a PNG, because vtracer's own WebP decoder
fails on lossless and transparent files and reads lossy ones as greyscale. Animated
WebPs trace their first frame.
"""

import io
from pathlib import Path
import vtracer
from PIL import Image

from image_convert import INPUT_DIR, OUTPUT_DIR, convert_images


def _trace(img: Image.Image, dest: Path) -> None:
    png = io.BytesIO()
    img.convert('RGBA').save(png, 'PNG')

    # vtracer's defaults. Raise filter_speckle here if lossy compression
    # artifacts are showing up as stray micro-paths, see the README.
    svg = vtracer.convert_raw_image_to_svg(png.getvalue(), img_format='png')
    dest.write_text(svg, encoding='utf-8')


def convert_webp_to_svg(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all WebP files in the input folder to SVG files in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_images(input_dir, output_dir, ('.webp',), ('.svg',), _trace)


if __name__ == "__main__":
    result = convert_webp_to_svg()
    if not result.startswith("Converted"):
        print(result)
