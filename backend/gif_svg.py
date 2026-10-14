"""Trace GIF images in input/ into vector SVG paths in output/ with vtracer.

Every frame is traced into its own SVG: name.svg for a static GIF, name_frame1.svg,
name_frame2.svg and so on for an animated one. The animation itself is not kept.
Pillow decodes each frame and vtracer is handed a PNG of it, since a GIF's later frames
only exist once Pillow has composited them onto the ones before.

Suits flat-color art, which is what most GIFs are. A photographic GIF traces slowly and
comes back as a huge SVG per frame.
"""

import io
import os
import glob
import vtracer
from PIL import Image, ImageSequence

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Folders
input_folder = os.path.join(script_dir, 'input')
output_folder = os.path.join(script_dir, 'output')


def _trace_frame(frame: Image.Image) -> str:
    """Trace one frame into SVG markup. Transparent areas stay transparent."""
    png = io.BytesIO()
    frame.convert('RGBA').save(png, 'PNG')
    # vtracer's defaults. Raise filter_speckle here if dithering is showing up as stray
    # micro-paths, see the README.
    return vtracer.convert_raw_image_to_svg(png.getvalue(), img_format='png')


def _write_svgs(svgs: list[str], filename: str) -> list[str]:
    """Write the traced frames to the output folder.

    Returns:
        The names of the SVG files written.
    """
    names = []
    for index, svg in enumerate(svgs, start=1):
        # A static GIF keeps the plain name, so the common case does not end up with a
        # pointless "_frame1" suffix.
        suffix = "" if len(svgs) == 1 else f"_frame{index}"
        svg_name = f"{filename}{suffix}.svg"
        svg_file = os.path.join(output_folder, svg_name)
        if os.path.exists(svg_file):
            print(f"Overwrote existing file: {svg_name}")

        with open(svg_file, 'w', encoding='utf-8') as f:
            f.write(svg)
        names.append(svg_name)
    return names


def convert_gif_to_svg() -> str:
    """Convert all GIF files in the input folder to SVG files in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """

    # Create output folder if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Both cases are globbed because glob matches with fnmatch, which is case-sensitive
    # on macOS and Linux whatever the filesystem does, so '*.gif' alone would miss
    # logo.GIF. A set rather than a concatenated list so that a file matching two
    # patterns is still converted once.
    gif_files = sorted({
        path
        for pattern in ('*.gif', '*.GIF')
        for path in glob.glob(os.path.join(input_folder, pattern))
    })

    if not gif_files:
        svg_present = glob.glob(os.path.join(input_folder, '*.svg'))
        if svg_present:
            return "That file is already in svg format"
        return "No GIF files found in input folder"

    converted = []
    errors = []

    for gif_file in gif_files:
        try:
            filename = os.path.splitext(os.path.basename(gif_file))[0]
            print(f"Converting {os.path.basename(gif_file)} to svg")

            # Every frame is traced before any file is written, so a frame that fails
            # does not leave a half-converted set behind.
            with Image.open(gif_file) as img:
                svgs = [_trace_frame(frame) for frame in ImageSequence.Iterator(img)]
            names = _write_svgs(svgs, filename)

            print(f"Converted {os.path.basename(gif_file)} to {', '.join(names)}")
            converted.extend(names)

        # Pillow raises on an unreadable file, but vtracer is a Rust extension that
        # panics on input it dislikes, and pyo3's PanicException derives from
        # BaseException, so `except Exception` never sees it and one bad file takes down
        # the whole batch. The class is not importable to name directly, hence the wide
        # catch with the interrupts re-raised first.
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException as e:
            print(f"Error converting {gif_file}: {str(e)}")
            errors.append(f"{os.path.basename(gif_file)}: {e}")

    if not converted:
        return f"No files converted. {len(errors)} failed: {'; '.join(errors)}"

    summary = f"Converted {len(converted)} file(s) to output/: {', '.join(converted)}"
    if errors:
        summary += f". {len(errors)} failed: {'; '.join(errors)}"
    return summary


if __name__ == "__main__":
    result = convert_gif_to_svg()
    if not result.startswith("Converted"):
        print(result)
