"""Tests for image_convert.upright and the EXIF orientation handling in convert_images."""

from pathlib import Path

from PIL import Image

import image_convert
import jpg_png


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
