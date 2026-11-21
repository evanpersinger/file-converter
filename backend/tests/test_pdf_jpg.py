"""Tests for pdf_jpg.py, which renders each PDF page to a JPG.

RENDER_DPI is lowered per test, so nothing here renders a real 300 DPI page.
"""

from pathlib import Path

import fitz
import pytest
from PIL import Image

import pdf_jpg

WorkDirs = tuple[Path, Path]


def write_pdf(path: Path, pages: int) -> None:
    with fitz.open() as document:
        for _ in range(pages):
            document.new_page(width=8.5 * 72, height=11 * 72)
        document.save(path)


def test_a_single_page_pdf_becomes_one_jpg_at_the_render_dpi(
    work_dirs: WorkDirs, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, output_dir = work_dirs
    monkeypatch.setattr(pdf_jpg, "RENDER_DPI", 100)
    write_pdf(input_dir / "page.pdf", pages=1)

    pdf_jpg.convert_pdf_to_jpg(input_dir, output_dir)

    with Image.open(output_dir / "page.jpg") as jpg:
        assert jpg.format == "JPEG"
        assert jpg.size == (850, 1100)


def test_a_multi_page_pdf_becomes_one_jpg_per_page(
    work_dirs: WorkDirs, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, output_dir = work_dirs
    monkeypatch.setattr(pdf_jpg, "RENDER_DPI", 50)
    write_pdf(input_dir / "book.pdf", pages=2)

    pdf_jpg.convert_pdf_to_jpg(input_dir, output_dir)

    assert sorted(path.name for path in output_dir.iterdir()) == [
        "book_page1.jpg",
        "book_page2.jpg",
    ]
