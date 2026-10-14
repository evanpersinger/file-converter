"""Tests for gif_svg.py, which traces every frame of a GIF into its own SVG with vtracer.

Same batch contract as webp_svg.py. The frame cases matter most: a static GIF keeps the
plain name, an animated one gets one numbered file per frame, and each file must hold
that frame's colors.
"""

import re
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest
from PIL import Image, ImageDraw

import gif_svg

Sandbox = Callable[[ModuleType], tuple[Path, Path]]
WriteImage = Callable[..., Path]


def fills(svg_file: Path) -> set[str]:
    return {f.upper() for f in re.findall(r'fill="#([0-9a-fA-F]{6})"', svg_file.read_text())}


def test_reports_when_input_is_empty(sandbox: Sandbox) -> None:
    sandbox(gif_svg)
    assert gif_svg.convert_gif_to_svg() == "No GIF files found in input folder"


def test_reports_when_the_file_is_already_an_svg(sandbox: Sandbox) -> None:
    input_dir, _ = sandbox(gif_svg)
    (input_dir / "logo.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>')

    assert gif_svg.convert_gif_to_svg() == "That file is already in svg format"


@pytest.mark.parametrize("filename", ["logo.gif", "logo.GIF"])
def test_a_static_gif_keeps_the_plain_name(
    sandbox: Sandbox, write_image: WriteImage, filename: str
) -> None:
    input_dir, output_dir = sandbox(gif_svg)
    write_image(input_dir / filename, "GIF")

    summary = gif_svg.convert_gif_to_svg()

    assert "logo.svg" in summary
    assert [p.name for p in output_dir.iterdir()] == ["logo.svg"]
    assert "<path" in (output_dir / "logo.svg").read_text()


def test_an_animated_gif_gives_one_svg_per_frame_in_order(sandbox: Sandbox) -> None:
    input_dir, output_dir = sandbox(gif_svg)
    frames = [Image.new("RGB", (40, 40), color) for color in ("red", "lime", "blue")]
    frames[0].save(
        input_dir / "anim.gif", "GIF", save_all=True, append_images=frames[1:], duration=100
    )

    summary = gif_svg.convert_gif_to_svg()

    assert "Converted 3 file(s)" in summary
    assert sorted(p.name for p in output_dir.iterdir()) == [
        "anim_frame1.svg", "anim_frame2.svg", "anim_frame3.svg",
    ]
    assert fills(output_dir / "anim_frame1.svg") == {"FF0000"}
    assert fills(output_dir / "anim_frame2.svg") == {"00FF00"}
    assert fills(output_dir / "anim_frame3.svg") == {"0000FF"}


def test_a_transparent_background_adds_no_shape(sandbox: Sandbox) -> None:
    input_dir, output_dir = sandbox(gif_svg)
    image = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle((10, 10, 30, 30), fill=(255, 0, 0, 255))
    image.save(input_dir / "clear.gif", "GIF")

    gif_svg.convert_gif_to_svg()

    svg = (output_dir / "clear.svg").read_text()
    assert svg.count("<path") == 1
    assert fills(output_dir / "clear.svg") == {"FF0000"}


def test_one_bad_file_does_not_stop_the_good_ones(
    sandbox: Sandbox, write_image: WriteImage
) -> None:
    input_dir, output_dir = sandbox(gif_svg)
    write_image(input_dir / "good.gif", "GIF")
    (input_dir / "broken.gif").write_bytes(b"this is not a gif")

    summary = gif_svg.convert_gif_to_svg()

    assert "good.svg" in summary
    assert "1 failed" in summary
    assert "broken.gif" in summary
    assert (output_dir / "good.svg").exists()
