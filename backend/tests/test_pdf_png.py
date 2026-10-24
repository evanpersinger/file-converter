"""Tests for pdf_png.py, which renders each PDF page to a PNG.

RENDER_DPI and MAX_PAGE_PIXELS are lowered per test, so nothing here renders a real 600 DPI
page.
"""

from pathlib import Path

import fitz
import pytest
from PIL import Image

import pdf_png

WorkDirs = tuple[Path, Path]


def write_pdf(path: Path, width_inches: float, height_inches: float) -> None:
    with fitz.open() as document:
        document.new_page(width=width_inches * 72, height=height_inches * 72)
        document.save(path)


def png_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as png:
        return png.size


def test_a_page_under_the_pixel_cap_renders_at_the_full_dpi(
    work_dirs: WorkDirs, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, output_dir = work_dirs
    monkeypatch.setattr(pdf_png, "RENDER_DPI", 100)
    monkeypatch.setattr(pdf_png, "MAX_PAGE_PIXELS", 1_000_000)
    write_pdf(input_dir / "page.pdf", 8.5, 11)

    pdf_png.convert_pdf_to_png(input_dir, output_dir)

    assert png_size(output_dir / "page.png") == (850, 1100)


def test_a_page_over_the_pixel_cap_renders_at_a_lower_dpi(
    work_dirs: WorkDirs, monkeypatch: pytest.MonkeyPatch
) -> None:
    """17 x 22 inches at 100 DPI is 3.7 million pixels, so it has to drop below the cap."""
    input_dir, output_dir = work_dirs
    monkeypatch.setattr(pdf_png, "RENDER_DPI", 100)
    monkeypatch.setattr(pdf_png, "MAX_PAGE_PIXELS", 1_000_000)
    write_pdf(input_dir / "poster.pdf", 17, 22)

    pdf_png.convert_pdf_to_png(input_dir, output_dir)

    width, height = png_size(output_dir / "poster.png")
    assert width * height <= 1_000_000
    assert width < 1700
