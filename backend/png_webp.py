"""Convert PNG images to WebP.

For each .png in input/, opens it with Pillow and saves a lossless .webp in output/, so no
pixels change. Transparency is kept.
"""

import os
from PIL import Image

from find_files import find_files

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Folders
input_folder = os.path.join(script_dir, 'input')
output_folder = os.path.join(script_dir, 'output')


def convert_png_to_webp() -> str:
    """Convert all PNG files in the input folder to WebP files in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """

    # Create output folder if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    png_files = find_files(input_folder, '.png')

    if not png_files:
        webp_present = find_files(input_folder, '.webp')
        if webp_present:
            return "That file is already in webp format"
        return "No PNG files found in input folder"

    converted = []
    errors = []

    for png_file in png_files:
        try:
            filename = os.path.splitext(os.path.basename(png_file))[0]
            webp_file = os.path.join(output_folder, f"{filename}.webp")

            existed_before = os.path.exists(webp_file)
            print(f"Converting {os.path.basename(png_file)} to webp")

            with Image.open(png_file) as img:
                img.save(webp_file, 'WEBP', lossless=True)
            print(f"Converted {os.path.basename(png_file)} to {filename}.webp")
            if existed_before:
                print(f"Overwrote existing file: {filename}.webp")
            converted.append(f"{filename}.webp")

        except Exception as e:
            print(f"Error converting {png_file}: {str(e)}")
            errors.append(f"{os.path.basename(png_file)}: {e}")

    if not converted:
        return f"No files converted. {len(errors)} failed: {'; '.join(errors)}"

    summary = f"Converted {len(converted)} file(s) to output/: {', '.join(converted)}"
    if errors:
        summary += f". {len(errors)} failed: {'; '.join(errors)}"
    return summary


if __name__ == "__main__":
    result = convert_png_to_webp()
    if not result.startswith("Converted"):
        print(result)
