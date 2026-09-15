"""Convert HEIC images to JPG.

Registers the HEIF opener with Pillow, then for each .heic in input/ opens it,
converts to RGB, and saves a .jpg to output/.
"""

import os
import glob
from PIL import Image
import pillow_heif

# Register HEIF opener with Pillow so it can read .heic files
pillow_heif.register_heif_opener()

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Folders
input_folder = os.path.join(script_dir, 'input')
output_folder = os.path.join(script_dir, 'output')


def convert_heic_to_jpg() -> str:
    """Convert all HEIC files in the input folder to JPG files in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """

    # Create output folder if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Find all HEIC files (case-insensitive by checking both cases)
    heic_files = glob.glob(os.path.join(input_folder, '*.heic')) + \
                 glob.glob(os.path.join(input_folder, '*.HEIC'))

    # check for heic files
    if not heic_files:
        jpg_present = glob.glob(os.path.join(input_folder, '*.jpg')) + \
                      glob.glob(os.path.join(input_folder, '*.jpeg'))
        if jpg_present:
            return "That file is already in jpg format"
        return "No HEIC files found in input folder"

    converted = []
    errors = []

    for heic_file in heic_files:
        try:
            filename = os.path.splitext(os.path.basename(heic_file))[0]
            jpg_file = os.path.join(output_folder, f"{filename}.jpg")

            existed_before = os.path.exists(jpg_file)
            print(f"Converting {os.path.basename(heic_file)} to jpg")

            with Image.open(heic_file) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                img.save(jpg_file, 'JPEG', quality=95)
                print(f"Converted {os.path.basename(heic_file)} to {filename}.jpg")
                if existed_before:
                    print(f"Overwrote existing file: {filename}.jpg")
                converted.append(f"{filename}.jpg")

        except Exception as e:
            print(f"Error converting {heic_file}: {str(e)}")
            errors.append(f"{os.path.basename(heic_file)}: {e}")

    if not converted:
        return f"No files converted. {len(errors)} failed: {'; '.join(errors)}"

    summary = f"Converted {len(converted)} file(s) to output/: {', '.join(converted)}"
    if errors:
        summary += f". {len(errors)} failed: {'; '.join(errors)}"
    return summary


if __name__ == "__main__":
    result = convert_heic_to_jpg()
    if not result.startswith("Converted"):
        print(result)
