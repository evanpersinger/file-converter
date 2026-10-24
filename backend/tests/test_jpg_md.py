"""Tests for jpg_md.py, which OCRs each JPG and tidies the text into Markdown.

OCR is faked: what is under test is the tidying, not Tesseract.
"""

from collections.abc import Callable
from pathlib import Path

import pytest

import jpg_md

WorkDirs = tuple[Path, Path]
WriteImage = Callable[..., Path]


def test_a_lowercase_line_joins_the_one_before() -> None:
    assert jpg_md.clean_text("The quick brown\nfox jumps over") == "The quick brown fox jumps over"


def test_a_capitalized_line_stays_separate() -> None:
    assert jpg_md.clean_text("First sentence.\nSecond sentence.") == "First sentence.\nSecond sentence."


def test_runs_of_blank_lines_shrink_to_one() -> None:
    assert jpg_md.clean_text("Intro\n\n\n\nBody") == "Intro\n\nBody"


def test_trailing_and_repeated_spaces_are_removed() -> None:
    assert jpg_md.clean_text("two   words  \nNext") == "two words\nNext"


def test_empty_text_gives_an_empty_string() -> None:
    assert jpg_md.clean_text("") == ""


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
        jpg_md, "ocr_text", lambda image, **kwargs: "First sentence.\nsecond half\n\n\n\nThird"
    )

    summary = jpg_md.convert_jpg_to_markdown(input_dir, output_dir)

    assert "scan.md" in summary
    assert (output_dir / "scan.md").read_text(encoding="utf-8") == (
        "First sentence. second half\n\nThird"
    )
