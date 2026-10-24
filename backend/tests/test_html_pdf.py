"""Tests for html_pdf.py, which prints one HTML file to PDF with wkhtmltopdf or pandoc.

It has its own loop rather than convert_files: it returns True or False and prints. Which
tool it picks is not tested, so the real conversion only needs one of them.
"""

import shutil
from pathlib import Path

import fitz
import pytest

import html_pdf

WorkDirs = tuple[Path, Path]

needs_an_html_tool = pytest.mark.skipif(
    not (shutil.which("wkhtmltopdf") or (shutil.which("pandoc") and shutil.which("xelatex"))),
    reason="neither wkhtmltopdf nor pandoc with xelatex is installed",
)


def test_a_pdf_path_is_refused(
    work_dirs: WorkDirs, capsys: pytest.CaptureFixture[str]
) -> None:
    input_dir, output_dir = work_dirs

    assert html_pdf.convert_html_to_pdf("doc.pdf", None, input_dir, output_dir) is False
    assert "already in pdf format" in capsys.readouterr().out


def test_a_missing_file_gives_false(
    work_dirs: WorkDirs, capsys: pytest.CaptureFixture[str]
) -> None:
    input_dir, output_dir = work_dirs

    assert html_pdf.convert_html_to_pdf("ghost.html", None, input_dir, output_dir) is False
    assert "not found" in capsys.readouterr().out


@needs_an_html_tool
def test_a_page_becomes_a_pdf_with_its_text(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "page.html").write_text(
        "<html><head><title>Page</title></head>"
        "<body><h1>Hello page</h1><p>Some body text</p></body></html>",
        encoding="utf-8",
    )

    assert html_pdf.convert_html_to_pdf("page.html", None, input_dir, output_dir) is True

    with fitz.open(output_dir / "page.pdf") as pdf:
        text = pdf[0].get_text()
    assert "Hello page" in text and "Some body text" in text
