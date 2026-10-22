"""Convert JPG images in input/ to Markdown in output/ via Tesseract OCR.

English only (lang='eng'): other languages come back as garbled English, not an error.
"""

import pytesseract
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter
import re

from batch_convert import INPUT_DIR, OUTPUT_DIR
from image_convert import convert_images


def preprocess_image(image):
    """Preprocess image to improve OCR accuracy"""
    # Convert to grayscale for better OCR
    if image.mode != 'L':
        image = image.convert('L')
    
    # Enhance contrast
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(1.5)
    
    # Enhance sharpness
    enhancer = ImageEnhance.Sharpness(image)
    image = enhancer.enhance(1.2)
    
    # Apply slight denoising
    image = image.filter(ImageFilter.MedianFilter(size=3))
    
    return image


def clean_text(text):
    """Clean extracted text and format as markdown"""
    if not text:
        return ""
    
    # Remove excessive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Remove trailing whitespace from each line
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
        
        # Try to join with following lines that are continuations
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
    
    # Final cleanup
    text = re.sub(r' +', ' ', text)
    text = re.sub(r'\n +', '\n', text)
    
    return text.strip()


def _ocr_to_markdown(img: Image.Image, dest: Path) -> None:
    # Preprocess image for better OCR
    processed_image = preprocess_image(img)

    # OCR with better configuration for accuracy
    custom_config = r'--oem 3 --psm 6'
    text = pytesseract.image_to_string(
        processed_image,
        config=custom_config,
        lang='eng'
    )

    # Clean and format text as markdown
    dest.write_text(clean_text(text), encoding='utf-8')


def convert_jpg_to_markdown(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all JPG files in the input folder to Markdown files in the output folder.

    Uses OCR, so this reads text straight out of the image.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_images(
        input_dir, output_dir, ('.jpg', '.jpeg'), ('.md',), _ocr_to_markdown,
        target_label="markdown",
    )


if __name__ == "__main__":
    result = convert_jpg_to_markdown()
    if not result.startswith("Converted"):
        print(result)
