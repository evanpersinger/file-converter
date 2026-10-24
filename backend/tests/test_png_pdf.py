"""Tests for png_pdf.py, which writes each PNG to a one-page PDF at 100 DPI."""

from collections.abc import Callable
from pathlib import Path

import fitz
import pytest
from PIL import Image

import png_pdf

WorkDirs = tuple[Path, Path]
WriteImage = Callable[..., Path]


def test_reports_when_input_is_empty(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    assert (
        png_pdf.convert_png_to_pdf(input_dir, output_dir)
        == "No PNG files found in input folder"
    )


def test_reports_when_the_file_is_already_a_pdf(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "doc.pdf").write_bytes(b"%PDF-1.4")

    assert (
        png_pdf.convert_png_to_pdf(input_dir, output_dir)
        == "That file is already in pdf format"
    )


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


def test_an_existing_pdf_is_overwritten(
    work_dirs: WorkDirs, write_image: WriteImage
) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / "logo.png", "PNG")
    output_dir.mkdir()
    (output_dir / "logo.pdf").write_bytes(b"stale")

    png_pdf.convert_png_to_pdf(input_dir, output_dir)

    with fitz.open(output_dir / "logo.pdf") as document:
        assert document.page_count == 1


def test_one_bad_file_does_not_stop_the_good_ones(
    work_dirs: WorkDirs, write_image: WriteImage
) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / "good.png", "PNG")
    (input_dir / "broken.png").write_bytes(b"this is not a png")

    summary = png_pdf.convert_png_to_pdf(input_dir, output_dir)

    assert "good.pdf" in summary
    assert "1 failed" in summary
    assert "broken.png" in summary
    assert (output_dir / "good.pdf").exists()
