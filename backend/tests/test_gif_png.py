"""Tests for gif_png.py, which writes each GIF to a PNG.

The transparency and animation cases matter most: PNG can keep a GIF's transparent areas,
so they must survive the conversion, and an animated GIF has to give its first frame only.
"""

from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest
from PIL import Image, ImageDraw

import gif_png

Sandbox = Callable[[ModuleType], tuple[Path, Path]]
WriteImage = Callable[..., Path]


def test_reports_when_input_is_empty(sandbox: Sandbox) -> None:
    sandbox(gif_png)
    assert gif_png.convert_gif_to_png() == "No GIF files found in input folder"


def test_reports_when_the_file_is_already_a_png(
    sandbox: Sandbox, write_image: WriteImage
) -> None:
    input_dir, _ = sandbox(gif_png)
    write_image(input_dir / "photo.png", "PNG")

    assert gif_png.convert_gif_to_png() == "That file is already in png format"


@pytest.mark.parametrize("filename", ["logo.gif", "logo.GIF"])
def test_a_gif_becomes_a_png(
    sandbox: Sandbox, write_image: WriteImage, filename: str
) -> None:
    input_dir, output_dir = sandbox(gif_png)
    write_image(input_dir / filename, "GIF")

    summary = gif_png.convert_gif_to_png()

    assert "logo.png" in summary
    with Image.open(output_dir / "logo.png") as converted:
        assert converted.format == "PNG"


def test_transparency_is_kept(sandbox: Sandbox) -> None:
    input_dir, output_dir = sandbox(gif_png)
    image = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle((15, 15, 25, 25), fill=(255, 0, 0, 255))
    image.save(input_dir / "clear.gif", "GIF")

    gif_png.convert_gif_to_png()

    with Image.open(output_dir / "clear.png") as converted:
        rgba = converted.convert("RGBA")
    assert rgba.getpixel((2, 2))[3] == 0
    assert rgba.getpixel((20, 20)) == (255, 0, 0, 255)


def test_an_animated_gif_gives_only_its_first_frame(sandbox: Sandbox) -> None:
    input_dir, output_dir = sandbox(gif_png)
    frames = [Image.new("RGB", (40, 40), color) for color in ("red", "lime", "blue")]
    frames[0].save(
        input_dir / "anim.gif", "GIF", save_all=True, append_images=frames[1:], duration=100
    )

    gif_png.convert_gif_to_png()

    assert [path.name for path in output_dir.iterdir()] == ["anim.png"]
    with Image.open(output_dir / "anim.png") as converted:
        assert converted.convert("RGB").getpixel((20, 20)) == (255, 0, 0)


def test_one_bad_file_does_not_stop_the_good_ones(
    sandbox: Sandbox, write_image: WriteImage
) -> None:
    input_dir, output_dir = sandbox(gif_png)
    write_image(input_dir / "good.gif", "GIF")
    (input_dir / "broken.gif").write_bytes(b"this is not a gif")

    summary = gif_png.convert_gif_to_png()

    assert "good.png" in summary
    assert "1 failed" in summary
    assert "broken.gif" in summary
    assert (output_dir / "good.png").exists()
