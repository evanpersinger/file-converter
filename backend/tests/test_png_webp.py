"""Tests for png_webp.py, which writes each PNG to a lossless WebP.

Two things matter most: the conversion is lossless, so the pixels must come back identical,
and transparency must survive, including in palette PNGs, which store it differently.
"""

from collections.abc import Callable
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageDraw

import png_webp

WorkDirs = tuple[Path, Path]
WriteImage = Callable[..., Path]


def test_reports_when_input_is_empty(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    assert (
        png_webp.convert_png_to_webp(input_dir, output_dir)
        == "No PNG files found in input folder"
    )


def test_reports_when_the_file_is_already_a_webp(
    work_dirs: WorkDirs, write_image: WriteImage
) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / "photo.webp", "WEBP")

    assert (
        png_webp.convert_png_to_webp(input_dir, output_dir)
        == "That file is already in webp format"
    )


@pytest.mark.parametrize("filename", ["logo.png", "logo.PNG"])
def test_a_png_becomes_a_webp(
    work_dirs: WorkDirs, write_image: WriteImage, filename: str
) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / filename, "PNG")

    summary = png_webp.convert_png_to_webp(input_dir, output_dir)

    assert "logo.webp" in summary
    with Image.open(output_dir / "logo.webp") as converted:
        assert converted.format == "WEBP"


def test_the_pixels_are_unchanged(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    original = Image.new("RGB", (64, 64))
    original.putdata([(x * 4 % 256, y * 4 % 256, (x + y) * 2 % 256)
                      for y in range(64) for x in range(64)])
    original.save(input_dir / "gradient.png", "PNG")

    png_webp.convert_png_to_webp(input_dir, output_dir)

    with Image.open(output_dir / "gradient.webp") as converted:
        assert ImageChops.difference(converted.convert("RGB"), original).getbbox() is None


def test_transparency_is_kept(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    image = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle((15, 15, 25, 25), fill=(255, 0, 0, 255))
    image.save(input_dir / "clear.png", "PNG")

    png_webp.convert_png_to_webp(input_dir, output_dir)

    with Image.open(output_dir / "clear.webp") as converted:
        rgba = converted.convert("RGBA")
    assert rgba.getpixel((2, 2))[3] == 0
    assert rgba.getpixel((20, 20)) == (255, 0, 0, 255)


def test_transparency_is_kept_in_a_palette_png(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    image = Image.new("P", (40, 40), 0)
    image.putpalette([0, 0, 0, 255, 0, 0] + [0, 0, 0] * 254)
    ImageDraw.Draw(image).rectangle((15, 15, 25, 25), fill=1)
    image.save(input_dir / "indexed.png", "PNG", transparency=0)

    png_webp.convert_png_to_webp(input_dir, output_dir)

    with Image.open(output_dir / "indexed.webp") as converted:
        rgba = converted.convert("RGBA")
    assert rgba.getpixel((2, 2))[3] == 0
    assert rgba.getpixel((20, 20)) == (255, 0, 0, 255)


def test_one_bad_file_does_not_stop_the_good_ones(
    work_dirs: WorkDirs, write_image: WriteImage
) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / "good.png", "PNG")
    (input_dir / "broken.png").write_bytes(b"this is not a png")

    summary = png_webp.convert_png_to_webp(input_dir, output_dir)

    assert "good.webp" in summary
    assert "1 failed" in summary
    assert "broken.png" in summary
    assert (output_dir / "good.webp").exists()
