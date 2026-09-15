"""Convert JPG/JPEG images to PDF.

For each image in input/, opens it with Pillow, converts to RGB, and saves it as a
single-page PDF in output/.
"""

import os
import glob
from PIL import Image

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Folders
input_folder = os.path.join(script_dir, 'input')
output_folder = os.path.join(script_dir, 'output')


def convert_jpg_to_pdf() -> str:
    """Convert all JPG files in the input folder to PDF files in the output folder.

    Note: the image is embedded at 100 DPI with no text layer, so converting the
    resulting PDF onward to Markdown gives poor OCR. Use jpg_md.py for that instead.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """

    # Create output folder if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Find all JPG files
    jpg_files = glob.glob(os.path.join(input_folder, '*.jpg')) + \
                glob.glob(os.path.join(input_folder, '*.jpeg'))

    if not jpg_files:
        # If there are only PDFs present, notify the user those are already in target format
        pdf_present = glob.glob(os.path.join(input_folder, '*.pdf'))
        if pdf_present:
            return "That file is already in pdf format"
        return "No JPG files found in input folder"

    converted = []
    errors = []

    for jpg_file in jpg_files:
        try:
            # Get filename without extension
            filename = os.path.splitext(os.path.basename(jpg_file))[0]
            pdf_file = os.path.join(output_folder, f"{filename}.pdf")

            existed_before = os.path.exists(pdf_file)
            print(f"Converting {os.path.basename(jpg_file)} to pdf")

            # Open and convert image to PDF
            with Image.open(jpg_file) as img:
                # Convert to RGB if necessary (for PNG with transparency, etc.)
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                # Save as PDF
                img.save(pdf_file, "PDF", resolution=100.0)
                print(f"Converted {os.path.basename(jpg_file)} to {filename}.pdf")
                if existed_before:
                    print(f"Overwrote existing file: {filename}.pdf")
                converted.append(f"{filename}.pdf")

        except Exception as e:
            print(f"Error converting {jpg_file}: {str(e)}")
            errors.append(f"{os.path.basename(jpg_file)}: {e}")

    if not converted:
        return f"No files converted. {len(errors)} failed: {'; '.join(errors)}"

    summary = f"Converted {len(converted)} file(s) to output/: {', '.join(converted)}"
    if errors:
        summary += f". {len(errors)} failed: {'; '.join(errors)}"
    return summary

if __name__ == "__main__":
    result = convert_jpg_to_pdf()
    if not result.startswith("Converted"):
        print(result)

