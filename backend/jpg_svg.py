"""Trace JPG images in input/ into vector SVG paths in output/ with vtracer.

JPEG artifacts trace as real shapes, so prefer a PNG source when you have one.
"""

import io
from pathlib import Path
import vtracer
from PIL import Image

from batch_convert import INPUT_DIR, OUTPUT_DIR, convert_files
from image_convert import upright


def _trace(source: Path, dest: Path) -> None:
    with Image.open(source) as img:
        fixed = upright(img)
        if fixed is img:
            # vtracer's defaults. Raise filter_speckle here if JPEG edge artifacts
            # are showing up as stray micro-paths, see the README.
            vtracer.convert_image_to_svg_py(str(source), str(dest))
            return
        # vtracer reads a path itself and ignores the orientation tag, so a tagged photo
        # goes through Pillow first.
        png = io.BytesIO()
        fixed.convert("RGB").save(png, "PNG")
    dest.write_text(
        vtracer.convert_raw_image_to_svg(png.getvalue(), img_format="png"), encoding="utf-8"
    )


def convert_jpg_to_svg(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all JPG/JPEG files in the input folder to SVG files in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_files(input_dir, output_dir, ('.jpg', '.jpeg'), ('.svg',), _trace)


if __name__ == "__main__":
    result = convert_jpg_to_svg()
    if not result.startswith("Converted"):
        print(result)
