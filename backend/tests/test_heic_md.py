"""Tests for heic_md.py, which OCRs each HEIC to Markdown.

OCR is faked. heic_md has its own copy of jpg_md's clean_text, which test_jpg_md.py covers.
"""

from collections.abc import Callable
from pathlib import Path

import pytest

import heic_md

WorkDirs = tuple[Path, Path]
WriteImage = Callable[..., Path]


@pytest.mark.parametrize("filename", ["scan.heic", "scan.HEIC"])
def test_the_cleaned_text_is_written_to_a_md(
    work_dirs: WorkDirs,
    write_image: WriteImage,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / filename, "HEIF")
    monkeypatch.setattr(heic_md, "ocr_text", lambda image, **kwargs: "First sentence.\nsecond half\n")

    summary = heic_md.convert_heic_to_markdown(input_dir, output_dir)

    assert "scan.md" in summary
    assert (output_dir / "scan.md").read_text(encoding="utf-8") == "First sentence. second half"
