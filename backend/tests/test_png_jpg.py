"""Tests for png_jpg.py, which writes each PNG to a JPG.

The transparency case matters most: JPEG has no alpha, so a plain RGB conversion can turn
transparent areas black.
"""

from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest
from PIL import Image, ImageDraw

import png_jpg

Sandbox = Callable[[ModuleType], tuple[Path, Path]]
WriteImage = Callable[..., Path]


def test_reports_when_input_is_empty(sandbox: Sandbox) -> None:
    sandbox(png_jpg)
    assert png_jpg.convert_png_to_jpg() == "No PNG files found in input folder"


def test_reports_when_the_file_is_already_a_jpg(
    sandbox: Sandbox, write_image: WriteImage
) -> None:
    input_dir, _ = sandbox(png_jpg)
    write_image(input_dir / "photo.jpg", "JPEG")

    assert png_jpg.convert_png_to_jpg() == "That file is already in jpg format"


@pytest.mark.parametrize("filename", ["logo.png", "logo.PNG"])
def test_a_png_becomes_a_jpg(
    sandbox: Sandbox, write_image: WriteImage, filename: str
) -> None:
    input_dir, output_dir = sandbox(png_jpg)
    write_image(input_dir / filename, "PNG")

    summary = png_jpg.convert_png_to_jpg()

    assert "logo.jpg" in summary
    with Image.open(output_dir / "logo.jpg") as converted:
        assert converted.format == "JPEG"


def test_transparent_areas_come_out_white(sandbox: Sandbox) -> None:
    input_dir, output_dir = sandbox(png_jpg)
    image = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle((15, 15, 25, 25), fill=(255, 0, 0, 255))
    image.save(input_dir / "clear.png", "PNG")

    png_jpg.convert_png_to_jpg()

    with Image.open(output_dir / "clear.jpg") as converted:
        assert min(converted.getpixel((2, 2))) > 240


def test_one_bad_file_does_not_stop_the_good_ones(
    sandbox: Sandbox, write_image: WriteImage
) -> None:
    input_dir, output_dir = sandbox(png_jpg)
    write_image(input_dir / "good.png", "PNG")
    (input_dir / "broken.png").write_bytes(b"this is not a png")

    summary = png_jpg.convert_png_to_jpg()

    assert "good.jpg" in summary
    assert "1 failed" in summary
    assert "broken.png" in summary
    assert (output_dir / "good.jpg").exists()
