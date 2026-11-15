"""Tests for jpg_md.py, which OCRs each JPG into Markdown.

OCR is faked. The cleanup of the text is covered by test_image_md.py.
"""

from collections.abc import Callable
from pathlib import Path

import pytest

import image_md
import jpg_md

WorkDirs = tuple[Path, Path]
WriteImage = Callable[..., Path]


@pytest.mark.parametrize("filename", ["scan.jpg", "scan.jpeg", "scan.JPG"])
def test_the_cleaned_text_is_written_to_a_md(
    work_dirs: WorkDirs,
    write_image: WriteImage,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / filename)
    monkeypatch.setattr(
        image_md, "best_ocr_text", lambda image: "First sentence.\nsecond half\n\n\n\nThird"
    )

    summary = jpg_md.convert_jpg_to_markdown(input_dir, output_dir)

    assert "scan.md" in summary
    assert (output_dir / "scan.md").read_text(encoding="utf-8") == (
        "First sentence. second half\n\nThird"
    )
