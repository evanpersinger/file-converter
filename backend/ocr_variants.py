"""OCR an image a few ways and keep the reading Tesseract is most sure of.

jpg_md and heic_md used to run every image through a 3x3 median filter before OCR. That cleans
up noisy photos, but it also wears away the thin strokes of small text, so `1,234.56` could come
back as `1.734 46` with no warning. No single preprocessing wins on both clean small text and
noisy images, so this reads a few variants and keeps the one with the highest mean word
confidence from Tesseract.
"""

from PIL import Image, ImageEnhance, ImageFilter

from external_tool import ocr_data, ocr_text

OCR_CONFIG = r'--oem 3 --psm 6'

# Images up to this many pixels also get a 2x upscaled variant, which reads small text best.
# Bigger images (phone photos) skip it: their text is already many pixels tall, and tesseract
# on a 4x larger photo is slow.
UPSCALE_MAX_PIXELS = 4_000_000


def _enhanced(image: Image.Image) -> Image.Image:
    """Grayscale with a little extra contrast and sharpness."""
    gray = image.convert('L')
    gray = ImageEnhance.Contrast(gray).enhance(1.5)
    return ImageEnhance.Sharpness(gray).enhance(1.2)


def ocr_variants(image: Image.Image) -> list[Image.Image]:
    """The preprocessed images to try, most often the best first (it wins ties)."""
    base = _enhanced(image)
    # Median filtered: best on noisy images and on text big enough to survive it.
    variants = [base.filter(ImageFilter.MedianFilter(size=3))]
    # Unfiltered: keeps the thin strokes of small, clean text.
    variants.append(base)
    if base.width * base.height <= UPSCALE_MAX_PIXELS:
        # Upscaled, then filtered: small text that is also noisy.
        upscaled = base.resize((base.width * 2, base.height * 2), Image.LANCZOS)
        variants.append(upscaled.filter(ImageFilter.MedianFilter(size=3)))
    return variants


def mean_confidence(image: Image.Image) -> float:
    """Tesseract's mean word confidence (0-100) for an image, or -1 when it finds no words."""
    data = ocr_data(image, config=OCR_CONFIG, lang='eng')
    confidences = [
        float(conf) for conf, word in zip(data['conf'], data['text'])
        if str(word).strip() and float(conf) >= 0
    ]
    return sum(confidences) / len(confidences) if confidences else -1.0


def best_ocr_text(image: Image.Image) -> str:
    """OCR each variant of the image and return the text of the most confident one."""
    variants = ocr_variants(image)
    scores = [mean_confidence(variant) for variant in variants]
    best = variants[scores.index(max(scores))]
    return ocr_text(best, config=OCR_CONFIG, lang='eng')
