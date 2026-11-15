"""Tests for ocr_variants.py, which OCRs a few preprocessed versions of an image and keeps
the one Tesseract is most confident about.
"""

import shutil

import pytest
from PIL import Image, ImageDraw, ImageFont

import ocr_variants

needs_tesseract = pytest.mark.skipif(
    shutil.which("tesseract") is None, reason="tesseract is not installed"
)

INVOICE = "Invoice total: 1,234.56 due 2026-11-03"


def _text_image(text: str, height: int) -> Image.Image:
    font = ImageFont.load_default(size=height)
    width = int(font.getlength(text)) + 40
    image = Image.new("RGB", (width, height * 3), "white")
    ImageDraw.Draw(image).text((20, height), text, fill="black", font=font)
    return image


def test_a_small_image_gets_an_upscaled_variant() -> None:
    variants = ocr_variants.ocr_variants(Image.new("RGB", (100, 50), "white"))

    assert [v.size for v in variants] == [(100, 50), (100, 50), (200, 100)]
    assert all(v.mode == "L" for v in variants)


def test_a_large_image_is_not_upscaled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ocr_variants, "UPSCALE_MAX_PIXELS", 100 * 50 - 1)

    variants = ocr_variants.ocr_variants(Image.new("RGB", (100, 50), "white"))

    assert [v.size for v in variants] == [(100, 50), (100, 50)]


def test_the_most_confident_variant_is_read(monkeypatch: pytest.MonkeyPatch) -> None:
    image = Image.new("RGB", (100, 50), "white")
    filtered, plain, upscaled = ocr_variants.ocr_variants(image)
    scores = {filtered.tobytes(): 40.0, plain.tobytes(): 90.0, upscaled.tobytes(): 70.0}
    monkeypatch.setattr(ocr_variants, "mean_confidence", lambda v: scores[v.tobytes()])
    monkeypatch.setattr(
        ocr_variants, "ocr_text",
        lambda v, **kwargs: "plain" if v.tobytes() == plain.tobytes() else "other",
    )

    assert ocr_variants.best_ocr_text(image) == "plain"


def test_a_tie_goes_to_the_filtered_variant(monkeypatch: pytest.MonkeyPatch) -> None:
    image = Image.new("RGB", (100, 50), "white")
    filtered = ocr_variants.ocr_variants(image)[0]
    monkeypatch.setattr(ocr_variants, "mean_confidence", lambda v: 80.0)
    monkeypatch.setattr(
        ocr_variants, "ocr_text",
        lambda v, **kwargs: "filtered" if v.tobytes() == filtered.tobytes() else "other",
    )

    assert ocr_variants.best_ocr_text(image) == "filtered"


def test_mean_confidence_skips_empty_words_and_minus_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ocr_variants, "ocr_data",
        lambda image, **kwargs: {"text": ["", "Hello", " ", "world"], "conf": [-1, 90, 95, 70]},
    )

    assert ocr_variants.mean_confidence(Image.new("L", (1, 1))) == 80.0


def test_mean_confidence_is_minus_one_with_no_words(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ocr_variants, "ocr_data", lambda image, **kwargs: {"text": ["", ""], "conf": [-1, -1]}
    )

    assert ocr_variants.mean_confidence(Image.new("L", (1, 1))) == -1.0


@needs_tesseract
@pytest.mark.parametrize("height", [12, 14])
def test_real_tesseract_reads_small_digits_correctly(height: int) -> None:
    # The median filter alone read 12-14 px text as "1.734 46 due 7076 1103" (#82)
    text = ocr_variants.best_ocr_text(_text_image(INVOICE, height))

    assert INVOICE in " ".join(text.split())
