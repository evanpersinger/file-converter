"""Convert JPG images in input/ to plain text in output/ via Tesseract OCR.

English only (lang='eng'): other languages come back as garbled English, not an error.
"""

import pytesseract
import shutil
from pathlib import Path
from PIL import Image

from batch_convert import INPUT_DIR, OUTPUT_DIR
from image_convert import convert_images

# Dynamically find tesseract executable
tesseract_path = shutil.which('tesseract')
if tesseract_path:
    pytesseract.pytesseract.tesseract_cmd = tesseract_path
else:
    print("Warning: tesseract not found in PATH. Make sure tesseract is installed and accessible.")


def _ocr_to_text(img: Image.Image, dest: Path) -> None:
    # Convert to RGB if needed
    if img.mode != 'RGB':
        img = img.convert('RGB')

    # Save as a temporary PNG for tesseract compatibility
    temp_png = dest.with_name(f"{dest.stem}_temp.png")
    img.save(temp_png, 'PNG')

    try:
        # Use pytesseract to extract text with better settings for accuracy
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(str(temp_png), config=custom_config, lang='eng')
    finally:
        # Clean up temporary PNG, including when OCR fails, so it can't pass as output
        temp_png.unlink()

    # Clean up extra whitespace
    dest.write_text(text.strip(), encoding='utf-8')


def convert_jpg_to_txt(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all JPG/JPEG files in the input folder to text files using OCR.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_images(
        input_dir, output_dir, ('.jpg', '.jpeg'), ('.txt',), _ocr_to_text,
        source_label="JPG/JPEG", target_label="text",
    )


if __name__ == "__main__":
    result = convert_jpg_to_txt()
    if not result.startswith("Converted"):
        print(result)
