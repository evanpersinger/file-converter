"""Trace PNG images in input/ into vector SVG paths in output/ with vtracer.

Suits flat-color art. Photos come back as huge, slow SVGs. Tuning knobs are in the README.
"""

import os
import vtracer

from find_files import find_files

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Folders
input_folder = os.path.join(script_dir, 'input')
output_folder = os.path.join(script_dir, 'output')


def convert_png_to_svg() -> str:
    """Convert all PNG files in the input folder to SVG files in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """

    # Create output folder if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    png_files = find_files(input_folder, '.png')

    if not png_files:
        svg_present = find_files(input_folder, '.svg')
        if svg_present:
            return "That file is already in svg format"
        return "No PNG files found in input folder"

    converted = []
    errors = []

    for png_file in png_files:
        try:
            filename = os.path.splitext(os.path.basename(png_file))[0]
            svg_file = os.path.join(output_folder, f"{filename}.svg")

            existed_before = os.path.exists(svg_file)
            print(f"Converting {os.path.basename(png_file)} to svg")

            # vtracer's defaults suit flat-color art. colormode, mode and
            # filter_speckle are the knobs to reach for otherwise, see the README.
            vtracer.convert_image_to_svg_py(png_file, svg_file)
            print(f"Converted {os.path.basename(png_file)} to {filename}.svg")
            if existed_before:
                print(f"Overwrote existing file: {filename}.svg")
            converted.append(f"{filename}.svg")

        # vtracer is a Rust extension: on an unreadable file it panics, and pyo3's
        # PanicException derives from BaseException, so `except Exception` never sees it
        # and one bad file takes down the whole batch. The class is not importable to
        # name directly, hence the wide catch with the interrupts re-raised first.
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException as e:
            print(f"Error converting {png_file}: {str(e)}")
            errors.append(f"{os.path.basename(png_file)}: {e}")

    if not converted:
        return f"No files converted. {len(errors)} failed: {'; '.join(errors)}"

    summary = f"Converted {len(converted)} file(s) to output/: {', '.join(converted)}"
    if errors:
        summary += f". {len(errors)} failed: {'; '.join(errors)}"
    return summary


if __name__ == "__main__":
    result = convert_png_to_svg()
    if not result.startswith("Converted"):
        print(result)
