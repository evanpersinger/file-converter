"""Tests for docx_pdf.py, which has headless LibreOffice render each Word file to a PDF.

The command is checked with a fake run_tool. The real runs are skipped without LibreOffice.
"""

import shutil
import subprocess
from pathlib import Path

import fitz
import pytest
from docx import Document
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

import docx_pdf
import pptx_pdf

WorkDirs = tuple[Path, Path]

needs_libreoffice = pytest.mark.skipif(
    not any(shutil.which(name) for name in ("libreoffice", "soffice")),
    reason="LibreOffice is not on PATH",
)


def test_libreoffice_is_told_to_read_the_file_as_word(
    work_dirs: WorkDirs, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "report.docx").write_bytes(b"placeholder")
    commands: list[list[str]] = []

    def run(command: list[str]) -> subprocess.CompletedProcess:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(pptx_pdf, "_find_libreoffice", lambda: "soffice")
    monkeypatch.setattr(pptx_pdf, "run_tool", run)

    docx_pdf.convert_docx_to_pdf(input_dir, output_dir)

    assert "--infilter=MS Word 2007 XML" in commands[0]
    assert commands[0][-1] == str(input_dir / "report.docx")


@needs_libreoffice
def test_real_libreoffice_keeps_inserted_text_list_numbers_and_markup_characters(
    work_dirs: WorkDirs,
) -> None:
    input_dir, output_dir = work_dirs
    document = Document()
    paragraph = document.add_paragraph("before ")
    paragraph._p.append(parse_xml(
        f'<w:ins {nsdecls("w")} w:id="1" w:author="a" w:date="2026-01-01T00:00:00Z">'
        "<w:r><w:t>inserted</w:t></w:r></w:ins>"
    ))
    document.add_paragraph("alpha item", style="List Number")
    document.add_table(rows=1, cols=1).cell(0, 0).text = "x<y"
    document.save(input_dir / "report.docx")

    summary = docx_pdf.convert_docx_to_pdf(input_dir, output_dir)

    assert "report.pdf" in summary
    with fitz.open(output_dir / "report.pdf") as pdf:
        text = pdf[0].get_text()
    assert all(part in text for part in ("inserted", "1.", "alpha item", "x<y"))


@needs_libreoffice
def test_real_libreoffice_refuses_a_file_that_is_not_word(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "junk.docx").write_bytes(b"not a Word file")

    summary = docx_pdf.convert_docx_to_pdf(input_dir, output_dir)

    assert summary.startswith("No files converted. 1 failed: junk.docx")
    assert not (output_dir / "junk.pdf").exists()
