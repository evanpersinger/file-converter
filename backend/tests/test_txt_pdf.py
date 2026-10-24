"""Tests for txt_pdf.py, which builds a titled PDF from one text file.

It has its own loop rather than convert_files: it returns True or False and prints.
"""

from pathlib import Path

import fitz
import pytest

import txt_pdf

WorkDirs = tuple[Path, Path]


def pdf_text(path: Path) -> str:
    with fitz.open(path) as document:
        return "".join(page.get_text() for page in document)


def test_a_txt_becomes_a_pdf_with_a_title_and_its_lines(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "notes.txt").write_text("first line\nsecond line\n", encoding="utf-8")

    assert txt_pdf.convert_txt_to_pdf("notes.txt", None, input_dir, output_dir) is True

    text = pdf_text(output_dir / "notes.pdf")
    assert "Text File: notes" in text
    assert "first line" in text and "second line" in text


def test_the_output_name_can_be_chosen(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "notes.txt").write_text("hello", encoding="utf-8")

    txt_pdf.convert_txt_to_pdf("notes.txt", "renamed.pdf", input_dir, output_dir)

    assert (output_dir / "renamed.pdf").exists()
    assert not (output_dir / "notes.pdf").exists()


def test_a_pdf_path_is_refused(
    work_dirs: WorkDirs, capsys: pytest.CaptureFixture[str]
) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "doc.pdf").write_bytes(b"%PDF-1.4")

    assert txt_pdf.convert_txt_to_pdf("doc.pdf", None, input_dir, output_dir) is False
    assert "already in pdf format" in capsys.readouterr().out


def test_a_missing_file_gives_false_and_no_pdf(
    work_dirs: WorkDirs, capsys: pytest.CaptureFixture[str]
) -> None:
    input_dir, output_dir = work_dirs

    assert txt_pdf.convert_txt_to_pdf("ghost.txt", None, input_dir, output_dir) is False
    assert "not found" in capsys.readouterr().out
    assert list(output_dir.iterdir()) == []


def test_a_windows_1252_file_is_read(work_dirs: WorkDirs) -> None:
    """Not valid UTF-8, so the converter has to fall back instead of failing."""
    input_dir, output_dir = work_dirs
    (input_dir / "legacy.txt").write_bytes("café".encode("cp1252"))

    assert txt_pdf.convert_txt_to_pdf("legacy.txt", None, input_dir, output_dir) is True
    assert "café" in pdf_text(output_dir / "legacy.pdf")


def test_leading_spaces_keep_their_indent(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "code.txt").write_text("flush\n        indented\n", encoding="utf-8")

    txt_pdf.convert_txt_to_pdf("code.txt", None, input_dir, output_dir)

    with fitz.open(output_dir / "code.pdf") as document:
        left_edge = {word[4]: word[0] for word in document[0].get_text("words")}
    assert left_edge["indented"] > left_edge["flush"] + 20


def test_markup_characters_are_printed_as_text(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "math.txt").write_text("1 < 2 & 3 > 2 <b>not bold</b>", encoding="utf-8")

    assert txt_pdf.convert_txt_to_pdf("math.txt", None, input_dir, output_dir) is True
    assert "1 < 2 & 3 > 2 <b>not bold</b>" in pdf_text(output_dir / "math.pdf")


def test_an_existing_pdf_is_overwritten(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "notes.txt").write_text("hello", encoding="utf-8")
    output_dir.mkdir()
    (output_dir / "notes.pdf").write_bytes(b"stale")

    assert txt_pdf.convert_txt_to_pdf("notes.txt", None, input_dir, output_dir) is True
    assert "hello" in pdf_text(output_dir / "notes.pdf")
