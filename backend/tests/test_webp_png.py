"""Tests for webp_png.py, which writes each WebP to a PNG.

The transparency and animation cases matter most: PNG can keep the alpha channel, so it must
survive the conversion, and an animated WebP has to give its first frame only. Lossless saves
keep the test colors exact.
"""

from collections.abc import Callable
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

import webp_png

WorkDirs = tuple[Path, Path]
WriteImage = Callable[..., Path]


def test_reports_when_input_is_empty(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    assert (
        webp_png.convert_webp_to_png(input_dir, output_dir)
        == "No WEBP files found in input folder"
    )


def test_reports_when_the_file_is_already_a_png(
    work_dirs: WorkDirs, write_image: WriteImage
) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / "photo.png", "PNG")

    assert (
        webp_png.convert_webp_to_png(input_dir, output_dir)
        == "That file is already in png format"
    )


@pytest.mark.parametrize("filename", ["logo.webp", "logo.WEBP"])
def test_a_webp_becomes_a_png(
    work_dirs: WorkDirs, write_image: WriteImage, filename: str
) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / filename, "WEBP")

    summary = webp_png.convert_webp_to_png(input_dir, output_dir)

    assert "logo.png" in summary
    with Image.open(output_dir / "logo.png") as converted:
        assert converted.format == "PNG"


def test_transparency_is_kept(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    image = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle((15, 15, 25, 25), fill=(255, 0, 0, 255))
    image.save(input_dir / "clear.webp", "WEBP", lossless=True)

    webp_png.convert_webp_to_png(input_dir, output_dir)

    with Image.open(output_dir / "clear.png") as converted:
        rgba = converted.convert("RGBA")
    assert rgba.getpixel((2, 2))[3] == 0
    assert rgba.getpixel((20, 20)) == (255, 0, 0, 255)


def test_an_animated_webp_gives_only_its_first_frame(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    frames = [Image.new("RGB", (40, 40), color) for color in ("red", "lime", "blue")]
    frames[0].save(
        input_dir / "anim.webp",
        "WEBP",
        save_all=True,
        append_images=frames[1:],
        duration=100,
        lossless=True,
    )

    webp_png.convert_webp_to_png(input_dir, output_dir)

    assert [path.name for path in output_dir.iterdir()] == ["anim.png"]
    with Image.open(output_dir / "anim.png") as converted:
        assert converted.convert("RGB").getpixel((20, 20)) == (255, 0, 0)


def test_one_bad_file_does_not_stop_the_good_ones(
    work_dirs: WorkDirs, write_image: WriteImage
) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / "good.webp", "WEBP")
    (input_dir / "broken.webp").write_bytes(b"this is not a webp")

    summary = webp_png.convert_webp_to_png(input_dir, output_dir)

    assert "good.png" in summary
    assert "1 failed" in summary
    assert "broken.webp" in summary
    assert (output_dir / "good.png").exists()
