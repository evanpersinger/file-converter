"""Tests for png_jpg.py, which writes each PNG to a JPG.

The transparency case matters most: JPEG has no alpha, so a plain RGB conversion can turn
transparent areas black.
"""

from collections.abc import Callable
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

import png_jpg

WorkDirs = tuple[Path, Path]
WriteImage = Callable[..., Path]


def test_reports_when_input_is_empty(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    assert (
        png_jpg.convert_png_to_jpg(input_dir, output_dir) == "No PNG files found in input folder"
    )


def test_reports_when_the_file_is_already_a_jpg(
    work_dirs: WorkDirs, write_image: WriteImage
) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / "photo.jpg", "JPEG")

    assert (
        png_jpg.convert_png_to_jpg(input_dir, output_dir) == "That file is already in jpg format"
    )


@pytest.mark.parametrize("filename", ["logo.png", "logo.PNG"])
def test_a_png_becomes_a_jpg(
    work_dirs: WorkDirs, write_image: WriteImage, filename: str
) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / filename, "PNG")

    summary = png_jpg.convert_png_to_jpg(input_dir, output_dir)

    assert "logo.jpg" in summary
    with Image.open(output_dir / "logo.jpg") as converted:
        assert converted.format == "JPEG"


def test_transparent_areas_come_out_white(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    image = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle((15, 15, 25, 25), fill=(255, 0, 0, 255))
    image.save(input_dir / "clear.png", "PNG")

    png_jpg.convert_png_to_jpg(input_dir, output_dir)

    with Image.open(output_dir / "clear.jpg") as converted:
        assert min(converted.getpixel((2, 2))) > 240


def test_one_bad_file_does_not_stop_the_good_ones(
    work_dirs: WorkDirs, write_image: WriteImage
) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / "good.png", "PNG")
    (input_dir / "broken.png").write_bytes(b"this is not a png")

    summary = png_jpg.convert_png_to_jpg(input_dir, output_dir)

    assert "good.jpg" in summary
    assert "1 failed" in summary
    assert "broken.png" in summary
    assert (output_dir / "good.jpg").exists()
