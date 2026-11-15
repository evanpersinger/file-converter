"""Convert PNG, GIF, BMP, TIFF and WebP images in input/ to Markdown in output/ via Tesseract OCR.

English only (lang='eng'): other languages come back as garbled English, not an error.
Also holds clean_text and ocr_to_markdown, which jpg_md and heic_md share.
"""

import re
from pathlib import Path
from PIL import Image

from batch_convert import INPUT_DIR, OUTPUT_DIR
from image_convert import convert_images
from ocr_variants import best_ocr_text

SOURCE_EXTS = ('.png', '.gif', '.bmp', '.tiff', '.webp')


def clean_text(text):
    """Clean extracted text and format as markdown"""
    if not text:
        return ""

    text = re.sub(r'\n{3,}', '\n\n', text)

    lines = [line.rstrip() for line in text.split('\n')]

    # Join lines that are clearly part of the same sentence
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


def ocr_to_markdown(img: Image.Image, dest: Path) -> None:
    # Reads a few preprocessed versions and keeps the most confident (see ocr_variants)
    text = best_ocr_text(img)
    dest.write_text(clean_text(text), encoding='utf-8')


def convert_image_to_markdown(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all PNG, GIF, BMP, TIFF and WebP files in the input folder to Markdown files.

    Uses OCR, so this reads text straight out of the image. A GIF or TIFF with several
    frames or pages has only its first one read.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_images(
        input_dir, output_dir, SOURCE_EXTS, ('.md',), ocr_to_markdown, target_label="markdown"
    )


if __name__ == "__main__":
    result = convert_image_to_markdown()
    if not result.startswith("Converted"):
        print(result)
