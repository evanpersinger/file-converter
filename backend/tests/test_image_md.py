"""Tests for image_md.py, which OCRs each PNG, GIF, BMP, TIFF or WebP into Markdown.

OCR is faked: the tidying is covered by test_jpg_md, which image_md shares it with.
"""

from collections.abc import Callable
from pathlib import Path

import pytest

import image_md

WorkDirs = tuple[Path, Path]
WriteImage = Callable[..., Path]


@pytest.mark.parametrize(
    ("filename", "fmt"),
    [
        ("scan.png", "PNG"),
        ("scan.gif", "GIF"),
        ("scan.bmp", "BMP"),
        ("scan.tiff", "TIFF"),
        ("scan.webp", "WEBP"),
        ("scan.PNG", "PNG"),
    ],
)
def test_the_cleaned_text_is_written_to_a_md(
    work_dirs: WorkDirs,
    write_image: WriteImage,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
    fmt: str,
) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / filename, fmt)
    monkeypatch.setattr(
        image_md, "best_ocr_text", lambda image: "First sentence.\nsecond half\n\n\n\nThird"
    )

    summary = image_md.convert_image_to_markdown(input_dir, output_dir)

    assert "scan.md" in summary
    assert (output_dir / "scan.md").read_text(encoding="utf-8") == (
        "First sentence. second half\n\nThird"
    )
