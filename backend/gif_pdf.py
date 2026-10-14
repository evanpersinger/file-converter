"""Convert GIF images to PDF.

For each .gif in input/, opens it with Pillow and saves a PDF in output/ with one page
per frame, so a static GIF gives a single page and a 100-frame GIF gives 100. Each frame
is flattened onto white, because converting straight to RGB turns transparent areas black.
"""

import os
import glob
from PIL import Image, ImageSequence

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Folders
input_folder = os.path.join(script_dir, 'input')
output_folder = os.path.join(script_dir, 'output')


def _flatten_on_white(frame: Image.Image) -> Image.Image:
    """Return the frame as an RGB image with any transparency painted white."""
    rgba = frame.convert('RGBA')
    page = Image.new('RGB', rgba.size, 'white')
    page.paste(rgba, mask=rgba.getchannel('A'))
    return page


def convert_gif_to_pdf() -> str:
    """Convert all GIF files in the input folder to PDF files in the output folder.

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
        # If there are only PDFs present, notify the user those are already in target format
        pdf_present = glob.glob(os.path.join(input_folder, '*.pdf'))
        if pdf_present:
            return "That file is already in pdf format"
        return "No GIF files found in input folder"

    converted = []
    errors = []

    for gif_file in gif_files:
        try:
            filename = os.path.splitext(os.path.basename(gif_file))[0]
            pdf_file = os.path.join(output_folder, f"{filename}.pdf")

            existed_before = os.path.exists(pdf_file)
            print(f"Converting {os.path.basename(gif_file)} to pdf")

            with Image.open(gif_file) as img:
                pages = [_flatten_on_white(frame) for frame in ImageSequence.Iterator(img)]

            pages[0].save(
                pdf_file, "PDF", save_all=True, append_images=pages[1:], resolution=100.0
            )
            print(f"Converted {os.path.basename(gif_file)} to {filename}.pdf")
            if existed_before:
                print(f"Overwrote existing file: {filename}.pdf")
            converted.append(f"{filename}.pdf")

        except Exception as e:
            print(f"Error converting {gif_file}: {str(e)}")
            errors.append(f"{os.path.basename(gif_file)}: {e}")

    if not converted:
        return f"No files converted. {len(errors)} failed: {'; '.join(errors)}"

    summary = f"Converted {len(converted)} file(s) to output/: {', '.join(converted)}"
    if errors:
        summary += f". {len(errors)} failed: {'; '.join(errors)}"
    return summary


if __name__ == "__main__":
    result = convert_gif_to_pdf()
    if not result.startswith("Converted"):
        print(result)
