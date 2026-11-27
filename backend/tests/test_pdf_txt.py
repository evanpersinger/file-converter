"""Tests for pdf_txt.py, which turns a PDF into plain text.

OCR is replaced in every test, so none of them needs Tesseract.
"""

from pathlib import Path

import fitz
import pytest

import pdf_md
import pdf_txt

WorkDirs = tuple[Path, Path]

SEARCHABLE_TEXT = "This page has plenty of real text on it."


def write_pdf(path: Path, page_texts: list[str]) -> None:
    """One page per entry. An empty entry is a blank page, which counts as scanned."""
    with fitz.open() as document:
        for text in page_texts:
            page = document.new_page()
            if text:
                page.insert_text((72, 72), text)
        document.save(path)


def test_a_searchable_page_is_read_without_ocr(
    work_dirs: WorkDirs, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, output_dir = work_dirs
    monkeypatch.setattr(pdf_md, "ocr_page", lambda page: pytest.fail("OCR was used"))
    write_pdf(input_dir / "doc.pdf", [SEARCHABLE_TEXT])

    pdf_txt.convert_pdf_to_txt(input_dir, output_dir)

    assert (output_dir / "doc.txt").read_text(encoding="utf-8") == SEARCHABLE_TEXT + "\n"


def test_a_page_with_no_text_is_ocred_and_stays_in_page_order(
    work_dirs: WorkDirs, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, output_dir = work_dirs
    monkeypatch.setattr(pdf_md, "ocr_page", lambda page: "words from the scan")
    write_pdf(input_dir / "mixed.pdf", [SEARCHABLE_TEXT, ""])

    pdf_txt.convert_pdf_to_txt(input_dir, output_dir)

    assert (output_dir / "mixed.txt").read_text(encoding="utf-8") == (
        f"{SEARCHABLE_TEXT}\n\nwords from the scan\n"
    )


def test_a_password_protected_pdf_is_reported_as_failed(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    with fitz.open() as document:
        document.new_page().insert_text((72, 72), SEARCHABLE_TEXT)
        document.save(
            input_dir / "locked.pdf",
            encryption=fitz.PDF_ENCRYPT_AES_256,
            user_pw="secret",
            owner_pw="owner",
        )

    summary = pdf_txt.convert_pdf_to_txt(input_dir, output_dir)

    assert "locked.pdf: PDF is password protected" in summary
    assert not (output_dir / "locked.txt").exists()
