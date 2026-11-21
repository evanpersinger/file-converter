"""Tests for pdf_docx.py, which turns a PDF into a Word document with pdf2docx."""

from pathlib import Path

import fitz
from docx import Document

import pdf_docx

WorkDirs = tuple[Path, Path]

PAGE_TEXT = "Quarterly report for the whole team."


def write_pdf(path: Path, **save_options: object) -> None:
    with fitz.open() as document:
        document.new_page().insert_text((72, 72), PAGE_TEXT)
        document.save(path, **save_options)


def test_the_text_of_a_pdf_lands_in_the_word_file(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    write_pdf(input_dir / "report.pdf")

    pdf_docx.convert_pdf_to_docx(input_dir, output_dir)

    paragraphs = [p.text for p in Document(str(output_dir / "report.docx")).paragraphs]
    assert PAGE_TEXT in " ".join(paragraphs)


def test_a_password_protected_pdf_is_reported_as_failed(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    write_pdf(
        input_dir / "locked.pdf",
        encryption=fitz.PDF_ENCRYPT_AES_256,
        user_pw="secret",
        owner_pw="owner",
    )

    summary = pdf_docx.convert_pdf_to_docx(input_dir, output_dir)

    assert "locked.pdf: PDF is password protected" in summary
    assert not (output_dir / "locked.docx").exists()
