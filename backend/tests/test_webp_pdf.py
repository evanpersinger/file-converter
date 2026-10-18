"""Tests for webp_pdf.py, which writes each WebP to a PDF with one page per frame.

The frame and transparency cases matter most: Pillow only saves an animated WebP's first
frame unless it is asked for all of them, and a plain RGB conversion turns transparent
areas black. Lossless saves keep the test colors exact.
"""

from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import fitz
import pytest
from PIL import Image, ImageDraw

import webp_pdf

Sandbox = Callable[[ModuleType], tuple[Path, Path]]
WriteImage = Callable[..., Path]


def center_pixel(page: fitz.Page) -> tuple[int, int, int]:
    pixmap = page.get_pixmap()
    return pixmap.pixel(pixmap.width // 2, pixmap.height // 2)


def test_reports_when_input_is_empty(sandbox: Sandbox) -> None:
    sandbox(webp_pdf)
    assert webp_pdf.convert_webp_to_pdf() == "No WEBP files found in input folder"


def test_reports_when_the_file_is_already_a_pdf(sandbox: Sandbox) -> None:
    input_dir, _ = sandbox(webp_pdf)
    (input_dir / "doc.pdf").write_bytes(b"%PDF-1.4")

    assert webp_pdf.convert_webp_to_pdf() == "That file is already in pdf format"


@pytest.mark.parametrize("filename", ["logo.webp", "logo.WEBP"])
def test_a_static_webp_gives_a_single_page(
    sandbox: Sandbox, write_image: WriteImage, filename: str
) -> None:
    input_dir, output_dir = sandbox(webp_pdf)
    write_image(input_dir / filename, "WEBP")

    summary = webp_pdf.convert_webp_to_pdf()

    assert "logo.pdf" in summary
    with fitz.open(output_dir / "logo.pdf") as document:
        assert document.page_count == 1


def test_an_animated_webp_gives_one_page_per_frame_in_order(sandbox: Sandbox) -> None:
    input_dir, output_dir = sandbox(webp_pdf)
    frames = [Image.new("RGB", (40, 40), color) for color in ("red", "lime", "blue")]
    frames[0].save(
        input_dir / "anim.webp",
        "WEBP",
        save_all=True,
        append_images=frames[1:],
        duration=100,
        lossless=True,
    )

    webp_pdf.convert_webp_to_pdf()

    with fitz.open(output_dir / "anim.pdf") as document:
        assert document.page_count == 3
        red, green, blue = (center_pixel(page) for page in document)
    assert red[0] > 200 and red[1] < 50 and red[2] < 50
    assert green[1] > 200 and green[0] < 50 and green[2] < 50
    assert blue[2] > 200 and blue[0] < 50 and blue[1] < 50


def test_transparent_areas_come_out_white(sandbox: Sandbox) -> None:
    input_dir, output_dir = sandbox(webp_pdf)
    image = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle((15, 15, 25, 25), fill=(255, 0, 0, 255))
    image.save(input_dir / "clear.webp", "WEBP", lossless=True)

    webp_pdf.convert_webp_to_pdf()

    with fitz.open(output_dir / "clear.pdf") as document:
        pixmap = document[0].get_pixmap()
        assert min(pixmap.pixel(2, 2)) > 240


def test_one_bad_file_does_not_stop_the_good_ones(
    sandbox: Sandbox, write_image: WriteImage
) -> None:
    input_dir, output_dir = sandbox(webp_pdf)
    write_image(input_dir / "good.webp", "WEBP")
    (input_dir / "broken.webp").write_bytes(b"this is not a webp")

    summary = webp_pdf.convert_webp_to_pdf()

    assert "good.pdf" in summary
    assert "1 failed" in summary
    assert "broken.webp" in summary
    assert (output_dir / "good.pdf").exists()
