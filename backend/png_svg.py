"""Trace PNG images in input/ into vector SVG paths in output/ with vtracer.

Suits flat-color art. Photos come back as huge, slow SVGs. Tuning knobs are in the README.
"""

from pathlib import Path
import vtracer

from image_convert import INPUT_DIR, OUTPUT_DIR, convert_files


def _trace(source: Path, dest: Path) -> None:
    # vtracer's defaults suit flat-color art. colormode, mode and
    # filter_speckle are the knobs to reach for otherwise, see the README.
    vtracer.convert_image_to_svg_py(str(source), str(dest))


def convert_png_to_svg(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all PNG files in the input folder to SVG files in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_files(input_dir, output_dir, ('.png',), ('.svg',), _trace)


if __name__ == "__main__":
    result = convert_png_to_svg()
    if not result.startswith("Converted"):
        print(result)
