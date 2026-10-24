"""Tests for png_pdf.py, which writes each PNG to a one-page PDF at 100 DPI."""

from collections.abc import Callable
from pathlib import Path

import fitz
import pytest
from PIL import Image

import png_pdf

WorkDirs = tuple[Path, Path]
WriteImage = Callable[..., Path]


@pytest.mark.parametrize("filename", ["logo.png", "logo.PNG"])
def test_a_png_becomes_a_single_page_pdf(
    work_dirs: WorkDirs, write_image: WriteImage, filename: str
) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / filename, "PNG")

    summary = png_pdf.convert_png_to_pdf(input_dir, output_dir)

    assert "logo.pdf" in summary
    with fitz.open(output_dir / "logo.pdf") as document:
        assert document.page_count == 1


def test_the_page_matches_the_image_at_100_dpi(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    Image.new("RGB", (100, 50), "red").save(input_dir / "wide.png")

    png_pdf.convert_png_to_pdf(input_dir, output_dir)

    with fitz.open(output_dir / "wide.pdf") as document:
        page = document[0]
        assert round(page.rect.width) == 72
        assert round(page.rect.height) == 36
        pixmap = page.get_pixmap()
        red, green, blue = pixmap.pixel(pixmap.width // 2, pixmap.height // 2)
    assert red > 200 and green < 50 and blue < 50


@pytest.mark.parametrize("mode", ["RGBA", "L", "P"])
def test_other_color_modes_convert(work_dirs: WorkDirs, mode: str) -> None:
    input_dir, output_dir = work_dirs
    Image.new(mode, (8, 8)).save(input_dir / "shape.png")

    png_pdf.convert_png_to_pdf(input_dir, output_dir)

    with fitz.open(output_dir / "shape.pdf") as document:
        assert document.page_count == 1
