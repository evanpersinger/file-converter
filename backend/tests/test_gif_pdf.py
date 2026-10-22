"""Tests for gif_pdf.py, which writes each GIF to a PDF with one page per frame.

The frame and transparency cases matter most: Pillow only saves a GIF's first frame
unless it is asked for all of them, and a plain RGB conversion turns transparent areas
black.
"""

from collections.abc import Callable
from pathlib import Path

import fitz
import pytest
from PIL import Image, ImageDraw

import gif_pdf

WorkDirs = tuple[Path, Path]
WriteImage = Callable[..., Path]


def center_pixel(page: fitz.Page) -> tuple[int, int, int]:
    pixmap = page.get_pixmap()
    return pixmap.pixel(pixmap.width // 2, pixmap.height // 2)


def test_reports_when_input_is_empty(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    assert (
        gif_pdf.convert_gif_to_pdf(input_dir, output_dir) == "No GIF files found in input folder"
    )


def test_reports_when_the_file_is_already_a_pdf(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "doc.pdf").write_bytes(b"%PDF-1.4")

    assert (
        gif_pdf.convert_gif_to_pdf(input_dir, output_dir) == "That file is already in pdf format"
    )


@pytest.mark.parametrize("filename", ["logo.gif", "logo.GIF"])
def test_a_static_gif_gives_a_single_page(
    work_dirs: WorkDirs, write_image: WriteImage, filename: str
) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / filename, "GIF")

    summary = gif_pdf.convert_gif_to_pdf(input_dir, output_dir)

    assert "logo.pdf" in summary
    with fitz.open(output_dir / "logo.pdf") as document:
        assert document.page_count == 1


def test_an_animated_gif_gives_one_page_per_frame_in_order(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    frames = [Image.new("RGB", (40, 40), color) for color in ("red", "lime", "blue")]
    frames[0].save(
        input_dir / "anim.gif", "GIF", save_all=True, append_images=frames[1:], duration=100
    )

    gif_pdf.convert_gif_to_pdf(input_dir, output_dir)

    with fitz.open(output_dir / "anim.pdf") as document:
        assert document.page_count == 3
        red, green, blue = (center_pixel(page) for page in document)
    assert red[0] > 200 and red[1] < 50 and red[2] < 50
    assert green[1] > 200 and green[0] < 50 and green[2] < 50
    assert blue[2] > 200 and blue[0] < 50 and blue[1] < 50


def test_transparent_areas_come_out_white(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    image = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle((15, 15, 25, 25), fill=(255, 0, 0, 255))
    image.save(input_dir / "clear.gif", "GIF")

    gif_pdf.convert_gif_to_pdf(input_dir, output_dir)

    with fitz.open(output_dir / "clear.pdf") as document:
        pixmap = document[0].get_pixmap()
        assert min(pixmap.pixel(2, 2)) > 240


def test_one_bad_file_does_not_stop_the_good_ones(
    work_dirs: WorkDirs, write_image: WriteImage
) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / "good.gif", "GIF")
    (input_dir / "broken.gif").write_bytes(b"this is not a gif")

    summary = gif_pdf.convert_gif_to_pdf(input_dir, output_dir)

    assert "good.pdf" in summary
    assert "1 failed" in summary
    assert "broken.gif" in summary
    assert (output_dir / "good.pdf").exists()
