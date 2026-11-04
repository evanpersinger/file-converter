"""Tests for image_convert.upright and the EXIF orientation handling in convert_images."""

import importlib
from pathlib import Path

import fitz
import pytest
from PIL import Image

import image_convert
import jpg_png
import png_pdf


def _rotated_jpg(path: Path) -> None:
    """A 20x10 image carrying EXIF orientation 6 (display rotated 90 degrees clockwise)."""
    img = Image.new("RGB", (20, 10), "red")
    exif = Image.Exif()
    exif[0x0112] = 6
    img.save(path, "JPEG", exif=exif)


def test_upright_applies_the_orientation_tag(tmp_path: Path) -> None:
    _rotated_jpg(tmp_path / "a.jpg")
    with Image.open(tmp_path / "a.jpg") as img:
        assert image_convert.upright(img).size == (10, 20)


def test_upright_returns_an_untagged_image_unchanged() -> None:
    img = Image.new("RGB", (20, 10))
    assert image_convert.upright(img) is img


def test_a_rotated_jpg_converts_to_an_upright_png(work_dirs: tuple[Path, Path]) -> None:
    input_dir, output_dir = work_dirs
    _rotated_jpg(input_dir / "phone.jpg")

    jpg_png.convert_jpg_to_png(input_dir, output_dir)

    with Image.open(output_dir / "phone.png") as out:
        assert out.size == (10, 20)


def _gray_16_bit_png(path: Path) -> None:
    """A 16-bit grayscale PNG at about 30% gray (20000 of 65535, 78 of 255 in 8-bit)."""
    Image.new("I;16", (4, 4), 20000).save(path, "PNG")


def test_eight_bit_scales_a_16_bit_image_instead_of_clipping_it() -> None:
    img = image_convert.eight_bit(Image.new("I;16", (2, 2), 20000))
    assert img.mode == "L"
    assert img.getpixel((0, 0)) == 78


def test_eight_bit_returns_an_8_bit_image_unchanged() -> None:
    img = Image.new("RGB", (2, 2))
    assert image_convert.eight_bit(img) is img


@pytest.mark.parametrize(
    ("module", "function", "ext"),
    [("png_jpg", "convert_png_to_jpg", ".jpg"), ("png_webp", "convert_png_to_webp", ".webp")],
)
def test_a_16_bit_png_keeps_its_brightness(
    work_dirs: tuple[Path, Path], module: str, function: str, ext: str
) -> None:
    """Pillow clips 16-bit values to 255 when converting, so this used to come out white."""
    input_dir, output_dir = work_dirs
    _gray_16_bit_png(input_dir / "scan.png")

    getattr(importlib.import_module(module), function)(input_dir, output_dir)

    with Image.open(output_dir / f"scan{ext}") as img:
        red, green, blue = img.convert("RGB").getpixel((2, 2))
        assert 70 <= red <= 86 and 70 <= green <= 86 and 70 <= blue <= 86


def test_a_16_bit_png_keeps_its_brightness_in_a_pdf(work_dirs: tuple[Path, Path]) -> None:
    input_dir, output_dir = work_dirs
    _gray_16_bit_png(input_dir / "scan.png")

    png_pdf.convert_png_to_pdf(input_dir, output_dir)

    pixmap = fitz.open(output_dir / "scan.pdf").load_page(0).get_pixmap()
    red, green, blue = pixmap.pixel(pixmap.width // 2, pixmap.height // 2)
    assert 70 <= red <= 86 and 70 <= green <= 86 and 70 <= blue <= 86
