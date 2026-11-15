"""Convert JPG images in input/ to plain text in output/ via Tesseract OCR.

English only (lang='eng'): other languages come back as garbled English, not an error.
"""

from pathlib import Path
from PIL import Image

from batch_convert import INPUT_DIR, OUTPUT_DIR
from external_tool import ocr_text
from image_convert import convert_images


def _ocr_to_text(img: Image.Image, dest: Path) -> None:
    # convert() hands tesseract a fresh RGB copy, without the JPEG's leftover format metadata
    text = ocr_text(img.convert('RGB'), config=r'--oem 3 --psm 6', lang='eng')
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
