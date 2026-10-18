"""Convert GIF images to PNG.

For each .gif in input/, opens it with Pillow and saves a .png in output/. Transparency
is kept, and animated GIFs give their first frame.
"""

import os
from PIL import Image

from find_files import find_files

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Folders
input_folder = os.path.join(script_dir, 'input')
output_folder = os.path.join(script_dir, 'output')


def convert_gif_to_png() -> str:
    """Convert all GIF files in the input folder to PNG files in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """

    # Create output folder if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    gif_files = find_files(input_folder, '.gif')

    if not gif_files:
        png_present = find_files(input_folder, '.png')
        if png_present:
            return "That file is already in png format"
        return "No GIF files found in input folder"

    converted = []
    errors = []

    for gif_file in gif_files:
        try:
            filename = os.path.splitext(os.path.basename(gif_file))[0]
            png_file = os.path.join(output_folder, f"{filename}.png")

            existed_before = os.path.exists(png_file)
            print(f"Converting {os.path.basename(gif_file)} to png")

            with Image.open(gif_file) as img:
                img.save(png_file, 'PNG')
            print(f"Converted {os.path.basename(gif_file)} to {filename}.png")
            if existed_before:
                print(f"Overwrote existing file: {filename}.png")
            converted.append(f"{filename}.png")

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
    result = convert_gif_to_png()
    if not result.startswith("Converted"):
        print(result)
