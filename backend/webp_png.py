"""Convert WebP images to PNG.

For each .webp in input/, opens it with Pillow and saves a .png in output/. Transparency
is kept, and animated WebPs give their first frame.
"""

import os
from PIL import Image

from find_files import find_files

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Folders
input_folder = os.path.join(script_dir, 'input')
output_folder = os.path.join(script_dir, 'output')


def convert_webp_to_png() -> str:
    """Convert all WebP files in the input folder to PNG files in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """

    # Create output folder if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    webp_files = find_files(input_folder, '.webp')

    if not webp_files:
        png_present = find_files(input_folder, '.png')
        if png_present:
            return "That file is already in png format"
        return "No WEBP files found in input folder"

    converted = []
    errors = []

    for webp_file in webp_files:
        try:
            filename = os.path.splitext(os.path.basename(webp_file))[0]
            png_file = os.path.join(output_folder, f"{filename}.png")

            existed_before = os.path.exists(png_file)
            print(f"Converting {os.path.basename(webp_file)} to png")

            with Image.open(webp_file) as img:
                img.save(png_file, 'PNG')
            print(f"Converted {os.path.basename(webp_file)} to {filename}.png")
            if existed_before:
                print(f"Overwrote existing file: {filename}.png")
            converted.append(f"{filename}.png")

        except Exception as e:
            print(f"Error converting {webp_file}: {str(e)}")
            errors.append(f"{os.path.basename(webp_file)}: {e}")

    if not converted:
        return f"No files converted. {len(errors)} failed: {'; '.join(errors)}"

    summary = f"Converted {len(converted)} file(s) to output/: {', '.join(converted)}"
    if errors:
        summary += f". {len(errors)} failed: {'; '.join(errors)}"
    return summary


if __name__ == "__main__":
    result = convert_webp_to_png()
    if not result.startswith("Converted"):
        print(result)
