"""Convert HEIC images in input/ to PDF in output/. Each image becomes a single-page PDF."""

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


def convert_heic_to_pdf() -> str:
    """Convert all HEIC files in the input folder to PDF files in the output folder.

    Note: the image is embedded at 100 DPI with no text layer, so converting the
    resulting PDF onward to Markdown gives poor OCR. Use heic_md.py for that instead.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """

    # Create output folder if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Both cases are globbed because glob matches with fnmatch, which is case-sensitive
    # on macOS and Linux whatever the filesystem does, so '*.heic' alone would miss
    # IMG_1.HEIC, which is how the camera names them. A set rather than a concatenated
    # list so that a file matching two patterns is still converted once.
    heic_files = sorted({
        path
        for pattern in ('*.heic', '*.HEIC')
        for path in glob.glob(os.path.join(input_folder, pattern))
    })

    if not heic_files:
        pdf_present = glob.glob(os.path.join(input_folder, '*.pdf'))
        if pdf_present:
            return "That file is already in pdf format"
        return "No HEIC files found in input folder"

    print(f"Found {len(heic_files)} HEIC files to convert")

    converted = []
    errors = []

    for heic_file in heic_files:
        try:
            filename = os.path.splitext(os.path.basename(heic_file))[0]
            pdf_file = os.path.join(output_folder, f"{filename}.pdf")

            with Image.open(heic_file) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                img.save(pdf_file, "PDF", resolution=100.0)
                print(f"Converted: {os.path.basename(heic_file)} -> {filename}.pdf")
                converted.append(f"{filename}.pdf")

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
    print(convert_heic_to_pdf())
