"""Trace JPG images in input/ into vector SVG paths in output/ with vtracer.

JPEG artifacts trace as real shapes, so prefer a PNG source when you have one.
"""

from pathlib import Path
import vtracer

from batch_convert import INPUT_DIR, OUTPUT_DIR, convert_files


def _trace(source: Path, dest: Path) -> None:
    # vtracer's defaults. Raise filter_speckle here if JPEG edge artifacts
    # are showing up as stray micro-paths, see the README.
    vtracer.convert_image_to_svg_py(str(source), str(dest))


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
