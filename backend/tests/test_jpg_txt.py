"""Tests for jpg_txt.py, which OCRs each JPG to a text file.

OCR is faked so the tests are exact; one case runs real Tesseract and is skipped without it.
"""

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

import jpg_txt

WorkDirs = tuple[Path, Path]
WriteImage = Callable[..., Path]

needs_tesseract = pytest.mark.skipif(
    shutil.which("tesseract") is None, reason="tesseract is not installed"
)


@pytest.mark.parametrize("filename", ["scan.jpg", "scan.jpeg", "scan.JPG"])
def test_the_text_is_stripped_and_written_to_a_txt(
    work_dirs: WorkDirs,
    write_image: WriteImage,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / filename)
    monkeypatch.setattr(jpg_txt, "ocr_text", lambda path, **kwargs: "  Hello world\n\n")

    summary = jpg_txt.convert_jpg_to_txt(input_dir, output_dir)

    assert "scan.txt" in summary
    assert (output_dir / "scan.txt").read_text(encoding="utf-8") == "Hello world"


def test_the_temp_png_is_gone_after_ocr(
    work_dirs: WorkDirs, write_image: WriteImage, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / "scan.jpg")
    existed_during_ocr = []

    def fake_ocr(path: str, **kwargs: object) -> str:
        existed_during_ocr.append(Path(path).exists())
        return "text"

    monkeypatch.setattr(jpg_txt, "ocr_text", fake_ocr)

    jpg_txt.convert_jpg_to_txt(input_dir, output_dir)

    assert existed_during_ocr == [True]
    assert [path.name for path in output_dir.iterdir()] == ["scan.txt"]


def test_the_temp_png_is_gone_when_ocr_fails(
    work_dirs: WorkDirs, write_image: WriteImage, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / "scan.jpg")

    def failing_ocr(path: str, **kwargs: object) -> str:
        raise RuntimeError("tesseract fell over")

    monkeypatch.setattr(jpg_txt, "ocr_text", failing_ocr)

    summary = jpg_txt.convert_jpg_to_txt(input_dir, output_dir)

    assert "1 failed" in summary
    assert list(output_dir.iterdir()) == []


@needs_tesseract
def test_real_tesseract_reads_the_text_in_the_image(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    image = Image.new("RGB", (700, 160), "white")
    ImageDraw.Draw(image).text(
        (20, 40), "Hello world", fill="black", font=ImageFont.load_default(size=70)
    )
    image.save(input_dir / "words.jpg")

    jpg_txt.convert_jpg_to_txt(input_dir, output_dir)

    assert "hello world" in (output_dir / "words.txt").read_text(encoding="utf-8").lower()
