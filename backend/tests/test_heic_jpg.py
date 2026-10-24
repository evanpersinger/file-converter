"""Tests for heic_jpg.py, which writes each HEIC to a JPG."""

from collections.abc import Callable
from pathlib import Path

import pytest
from PIL import Image

import heic_jpg

WorkDirs = tuple[Path, Path]
WriteImage = Callable[..., Path]


@pytest.mark.parametrize("filename", ["photo.heic", "photo.HEIC"])
def test_a_heic_becomes_a_jpg(
    work_dirs: WorkDirs, write_image: WriteImage, filename: str
) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / filename, "HEIF")

    summary = heic_jpg.convert_heic_to_jpg(input_dir, output_dir)

    assert "photo.jpg" in summary
    with Image.open(output_dir / "photo.jpg") as converted:
        assert converted.format == "JPEG"
        red, green, blue = converted.getpixel((4, 4))
    assert red > 200 and green < 50 and blue < 50
