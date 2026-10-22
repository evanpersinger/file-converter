"""Convert HEIC images in input/ to Markdown in output/ via Tesseract OCR.

English only (lang='eng'): other languages come back as garbled English, not an error.
"""

import re
from pathlib import Path
import pytesseract
import pillow_heif
from PIL import Image, ImageEnhance, ImageFilter

from batch_convert import INPUT_DIR, OUTPUT_DIR
from image_convert import convert_images

pillow_heif.register_heif_opener()


def preprocess_image(image):
    """Preprocess image to improve OCR accuracy"""
    if image.mode != 'L':
        image = image.convert('L')

    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(1.5)

    enhancer = ImageEnhance.Sharpness(image)
    image = enhancer.enhance(1.2)

    image = image.filter(ImageFilter.MedianFilter(size=3))

    return image



def clean_text(text):
    """Clean extracted text and format as markdown"""
    if not text:
        return ""

    text = re.sub(r'\n{3,}', '\n\n', text)

    lines = [line.rstrip() for line in text.split('\n')]

    # fix sentence structure
    fixed_lines = []
    i = 0
    while i < len(lines):
        current_line = lines[i]

        if not current_line.strip():
            fixed_lines.append(current_line)
            i += 1
            continue

        while i + 1 < len(lines):
            next_line = lines[i + 1]

            if not next_line.strip():
                break

            # check if next line starts with lowercase
            next_stripped = next_line.strip()
            starts_with_lowercase = next_stripped and next_stripped[0].islower()
            ends_with_continuation = re.search(r'[,;:—–-]\s*$', current_line)

            should_join = False
            if starts_with_lowercase:
                should_join = True
            elif ends_with_continuation and next_stripped and not next_stripped[0].isupper():
                should_join = True

            if should_join:
                current_line = current_line + ' ' + next_stripped
                i += 1
            else:
                break

        fixed_lines.append(current_line)
        i += 1

    text = '\n'.join(fixed_lines)
    text = re.sub(r' +', ' ', text)
    text = re.sub(r'\n +', '\n', text)

    return text.strip()


def _ocr_to_markdown(img: Image.Image, dest: Path) -> None:
    processed_image = preprocess_image(img)

    custom_config = r'--oem 3 --psm 6'
    text = pytesseract.image_to_string(
        processed_image,
        config=custom_config,
        lang='eng'
    )

    dest.write_text(clean_text(text), encoding='utf-8')


def convert_heic_to_markdown(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all HEIC files in the input folder to Markdown files in the output folder.

    Uses OCR and processes the HEIC in memory, so no intermediate JPG is written.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_images(
        input_dir, output_dir, ('.heic',), ('.md',), _ocr_to_markdown, target_label="markdown"
    )


if __name__ == "__main__":
    result = convert_heic_to_markdown()
    if not result.startswith("Converted"):
        print(result)
