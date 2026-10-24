"""Tests for heic_pdf.py, which writes each HEIC to a one-page PDF at 100 DPI."""

from collections.abc import Callable
from pathlib import Path

import fitz
import pytest
from PIL import Image

import heic_pdf

WorkDirs = tuple[Path, Path]
WriteImage = Callable[..., Path]


@pytest.mark.parametrize("filename", ["photo.heic", "photo.HEIC"])
def test_a_heic_becomes_a_single_page_pdf(
    work_dirs: WorkDirs, write_image: WriteImage, filename: str
) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / filename, "HEIF")

    summary = heic_pdf.convert_heic_to_pdf(input_dir, output_dir)

    assert "photo.pdf" in summary
    with fitz.open(output_dir / "photo.pdf") as document:
        assert document.page_count == 1


def test_the_page_matches_the_image_at_100_dpi(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    Image.new("RGB", (100, 50), "red").save(input_dir / "wide.heic", "HEIF")

    heic_pdf.convert_heic_to_pdf(input_dir, output_dir)

    with fitz.open(output_dir / "wide.pdf") as document:
        page = document[0]
        assert round(page.rect.width) == 72
        assert round(page.rect.height) == 36
        pixmap = page.get_pixmap()
        red, green, blue = pixmap.pixel(pixmap.width // 2, pixmap.height // 2)
    assert red > 200 and green < 50 and blue < 50
