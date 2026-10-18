"""Tests for jpg_webp.py, which writes each JPG to a WebP.

WebP is lossy at quality 95, so the color check allows some drift.
"""

from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest
from PIL import Image

import jpg_webp

Sandbox = Callable[[ModuleType], tuple[Path, Path]]
WriteImage = Callable[..., Path]


def test_reports_when_input_is_empty(sandbox: Sandbox) -> None:
    sandbox(jpg_webp)
    assert jpg_webp.convert_jpg_to_webp() == "No JPG files found in input folder"


def test_reports_when_the_file_is_already_a_webp(
    sandbox: Sandbox, write_image: WriteImage
) -> None:
    input_dir, _ = sandbox(jpg_webp)
    write_image(input_dir / "photo.webp", "WEBP")

    assert jpg_webp.convert_jpg_to_webp() == "That file is already in webp format"


@pytest.mark.parametrize("filename", ["photo.jpg", "photo.JPG", "photo.jpeg"])
def test_a_jpg_becomes_a_webp(
    sandbox: Sandbox, write_image: WriteImage, filename: str
) -> None:
    input_dir, output_dir = sandbox(jpg_webp)
    write_image(input_dir / filename, "JPEG")

    summary = jpg_webp.convert_jpg_to_webp()

    assert "photo.webp" in summary
    with Image.open(output_dir / "photo.webp") as converted:
        assert converted.format == "WEBP"


def test_the_picture_keeps_its_colors(sandbox: Sandbox) -> None:
    input_dir, output_dir = sandbox(jpg_webp)
    Image.new("RGB", (40, 40), (255, 0, 0)).save(input_dir / "red.jpg", "JPEG")

    jpg_webp.convert_jpg_to_webp()

    with Image.open(output_dir / "red.webp") as converted:
        red, green, blue = converted.convert("RGB").getpixel((20, 20))
    assert red > 230 and green < 25 and blue < 25


def test_one_bad_file_does_not_stop_the_good_ones(
    sandbox: Sandbox, write_image: WriteImage
) -> None:
    input_dir, output_dir = sandbox(jpg_webp)
    write_image(input_dir / "good.jpg", "JPEG")
    (input_dir / "broken.jpg").write_bytes(b"this is not a jpg")

    summary = jpg_webp.convert_jpg_to_webp()

    assert "good.webp" in summary
    assert "1 failed" in summary
    assert "broken.jpg" in summary
    assert (output_dir / "good.webp").exists()
