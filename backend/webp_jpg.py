"""Convert WebP images to JPG.

For each .webp in input/, opens it with Pillow and saves a .jpg in output/. JPEG has no
transparency, so transparent areas are painted white. Animated WebPs give their first frame.
"""

import os
from PIL import Image

from find_files import find_files

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


def convert_webp_to_jpg() -> str:
    """Convert all WebP files in the input folder to JPG files in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """

    # Create output folder if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    webp_files = find_files(input_folder, '.webp')

    if not webp_files:
        jpg_present = find_files(input_folder, '.jpg', '.jpeg')
        if jpg_present:
            return "That file is already in jpg format"
        return "No WEBP files found in input folder"

    converted = []
    errors = []

    for webp_file in webp_files:
        try:
            filename = os.path.splitext(os.path.basename(webp_file))[0]
            jpg_file = os.path.join(output_folder, f"{filename}.jpg")

            existed_before = os.path.exists(jpg_file)
            print(f"Converting {os.path.basename(webp_file)} to jpg")

            with Image.open(webp_file) as img:
                _flatten_on_white(img).save(jpg_file, 'JPEG', quality=95)
            print(f"Converted {os.path.basename(webp_file)} to {filename}.jpg")
            if existed_before:
                print(f"Overwrote existing file: {filename}.jpg")
            converted.append(f"{filename}.jpg")

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
    result = convert_webp_to_jpg()
    if not result.startswith("Converted"):
        print(result)
