"""Tests for webp_svg.py, which traces WebPs into vector paths with vtracer.

The same batch contract as png_svg.py. webp_svg decodes with Pillow and hands vtracer a
PNG, because vtracer's own WebP decoder fails on lossless and transparent files and
reads lossy ones as greyscale. The color and variant cases pin that.
"""

import re
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest
from PIL import Image, ImageDraw

import webp_svg

Sandbox = Callable[[ModuleType], tuple[Path, Path]]
WriteImage = Callable[..., Path]


def test_reports_when_input_is_empty(sandbox: Sandbox) -> None:
    sandbox(webp_svg)
    assert webp_svg.convert_webp_to_svg() == "No WEBP files found in input folder"


def test_reports_when_the_file_is_already_an_svg(sandbox: Sandbox) -> None:
    input_dir, _ = sandbox(webp_svg)
    (input_dir / "logo.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>')

    assert webp_svg.convert_webp_to_svg() == "That file is already in svg format"


@pytest.mark.parametrize("filename", ["logo.webp", "logo.WEBP"])
def test_traces_both_spellings_of_the_extension(
    sandbox: Sandbox, write_image: WriteImage, filename: str
) -> None:
    input_dir, output_dir = sandbox(webp_svg)
    write_image(input_dir / filename, "WEBP")

    summary = webp_svg.convert_webp_to_svg()

    assert "logo.svg" in summary
    svg = (output_dir / "logo.svg").read_text()
    assert "<svg" in svg
    assert "<path" in svg


def test_traces_several_files(sandbox: Sandbox, write_image: WriteImage) -> None:
    input_dir, output_dir = sandbox(webp_svg)
    write_image(input_dir / "one.webp", "WEBP")
    write_image(input_dir / "two.webp", "WEBP", color="blue")

    summary = webp_svg.convert_webp_to_svg()

    assert "Converted 2 file(s)" in summary
    assert sorted(p.name for p in output_dir.iterdir()) == ["one.svg", "two.svg"]


def test_colors_survive_the_trace(sandbox: Sandbox) -> None:
    """vtracer decoding a lossy WebP itself returned only greys for this image."""
    input_dir, output_dir = sandbox(webp_svg)
    image = Image.new("RGB", (200, 200), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 90, 90), fill=(220, 30, 30))
    draw.ellipse((100, 100, 180, 180), fill=(20, 140, 60))
    image.save(input_dir / "logo.webp", "WEBP", quality=80)

    webp_svg.convert_webp_to_svg()

    fills = re.findall(r'fill="#([0-9a-fA-F]{6})"', (output_dir / "logo.svg").read_text())
    channels = [[int(f[i:i + 2], 16) for i in (0, 2, 4)] for f in fills]
    assert any(max(rgb) - min(rgb) > 100 for rgb in channels)


@pytest.mark.parametrize("lossless", [False, True])
def test_a_transparent_webp_converts(sandbox: Sandbox, lossless: bool) -> None:
    """vtracer's own decoder fails on every transparent WebP and every lossless one."""
    input_dir, output_dir = sandbox(webp_svg)
    image = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle((2, 2, 12, 12), fill=(255, 0, 0, 200))
    image.save(input_dir / "clear.webp", "WEBP", lossless=lossless)

    summary = webp_svg.convert_webp_to_svg()

    assert "clear.svg" in summary
    assert "<path" in (output_dir / "clear.svg").read_text()


def test_an_unreadable_file_is_reported_rather_than_raised(sandbox: Sandbox) -> None:
    input_dir, _ = sandbox(webp_svg)
    (input_dir / "broken.webp").write_bytes(b"this is not a webp")

    summary = webp_svg.convert_webp_to_svg()

    assert summary.startswith("No files converted. 1 failed:")
    assert "broken.webp" in summary


def test_one_bad_file_does_not_stop_the_good_ones(
    sandbox: Sandbox, write_image: WriteImage
) -> None:
    input_dir, output_dir = sandbox(webp_svg)
    write_image(input_dir / "good.webp", "WEBP")
    (input_dir / "broken.webp").write_bytes(b"this is not a webp")

    summary = webp_svg.convert_webp_to_svg()

    assert "good.svg" in summary
    assert "1 failed" in summary
    assert (output_dir / "good.svg").exists()


def test_an_animated_webp_traces_its_first_frame(sandbox: Sandbox) -> None:
    input_dir, output_dir = sandbox(webp_svg)
    frames = [Image.new("RGB", (8, 8), color) for color in ("red", "blue")]
    frames[0].save(
        input_dir / "anim.webp", "WEBP", save_all=True, append_images=frames[1:]
    )

    summary = webp_svg.convert_webp_to_svg()

    assert "anim.svg" in summary
    assert (output_dir / "anim.svg").exists()
