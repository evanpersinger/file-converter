"""Trace WebP images in input/ into vector SVG paths in output/ with vtracer.

WebP is often lossy, which traces as noise, so prefer a PNG source when you have one.
Pillow decodes the file and vtracer is handed a PNG, because vtracer's own WebP decoder
fails on lossless and transparent files and reads lossy ones as greyscale. Animated
WebPs trace their first frame.
"""

import io
import os
import glob
import vtracer
from PIL import Image

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Folders
input_folder = os.path.join(script_dir, 'input')
output_folder = os.path.join(script_dir, 'output')


def convert_webp_to_svg() -> str:
    """Convert all WebP files in the input folder to SVG files in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """

    # Create output folder if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Both cases are globbed because glob matches with fnmatch, which is case-sensitive
    # on macOS and Linux whatever the filesystem does, so '*.webp' alone would miss
    # photo.WEBP. A set rather than a concatenated list so that a file matching two
    # patterns is still converted once.
    webp_files = sorted({
        path
        for pattern in ('*.webp', '*.WEBP')
        for path in glob.glob(os.path.join(input_folder, pattern))
    })

    if not webp_files:
        svg_present = glob.glob(os.path.join(input_folder, '*.svg'))
        if svg_present:
            return "That file is already in svg format"
        return "No WEBP files found in input folder"

    converted = []
    errors = []

    for webp_file in webp_files:
        try:
            filename = os.path.splitext(os.path.basename(webp_file))[0]
            svg_file = os.path.join(output_folder, f"{filename}.svg")

            existed_before = os.path.exists(svg_file)
            print(f"Converting {os.path.basename(webp_file)} to svg")

            with Image.open(webp_file) as image:
                png = io.BytesIO()
                image.convert('RGBA').save(png, 'PNG')

            # vtracer's defaults. Raise filter_speckle here if lossy compression
            # artifacts are showing up as stray micro-paths, see the README.
            svg = vtracer.convert_raw_image_to_svg(png.getvalue(), img_format='png')
            with open(svg_file, 'w', encoding='utf-8') as f:
                f.write(svg)
            print(f"Converted {os.path.basename(webp_file)} to {filename}.svg")
            if existed_before:
                print(f"Overwrote existing file: {filename}.svg")
            converted.append(f"{filename}.svg")

        # Pillow raises on an unreadable file, but vtracer is a Rust extension that
        # panics on input it dislikes, and pyo3's PanicException derives from
        # BaseException, so `except Exception` never sees it and one bad file takes down
        # the whole batch. The class is not importable to name directly, hence the wide
        # catch with the interrupts re-raised first.
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException as e:
            print(f"Error converting {webp_file}: {str(e)}")
            errors.append(f"{os.path.basename(webp_file)}: {e}")

    if not converted:
        return f"No files converted. {len(errors)} failed: {'; '.join(errors)}"

    summary = f"Converted {len(converted)} file(s) to output/: {', '.join(converted)}"
    if errors:
        summary += f". {len(errors)} failed: {'; '.join(errors)}"
    return summary


if __name__ == "__main__":
    result = convert_webp_to_svg()
    if not result.startswith("Converted"):
        print(result)
