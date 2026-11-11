"""Text files that are not UTF-8, like a script saved by an older Windows editor.

Each of these converters used to read with encoding='utf-8' and failed outright on such a
file with "'utf-8' codec can't decode byte 0xe9". They now go through
batch_convert.read_text, which falls back to Windows-1252.
"""

from pathlib import Path
import shutil

import pytest
from pypdf import PdfReader

import md_pdf
import md_toon
import R_Rmd
import Rmd_pdf
import sql_pdf
from batch_convert import read_text

WorkDirs = tuple[Path, Path]

needs_rmd_to_pdf = pytest.mark.skipif(
    not (shutil.which("Rscript") and shutil.which("xelatex")),
    reason="Rscript and xelatex are both needed to render an Rmd to PDF",
)


def _write_cp1252(path: Path, text: str) -> None:
    path.write_bytes(text.encode("cp1252"))


# read_text
# Dropping a BOM and falling back to Windows-1252 are already covered by test_csv_md.py
# and test_txt_pdf.py, which reach both through read_text.


def test_read_text_keeps_line_endings_unless_asked(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_bytes(b"one\r\ntwo\rthree\n")
    assert read_text(tmp_path / "a.txt") == "one\r\ntwo\rthree\n"
    assert read_text(tmp_path / "a.txt", translate_newlines=True) == "one\ntwo\nthree\n"


# The converters


def test_sql_pdf_reads_a_windows_1252_file(tmp_path: Path) -> None:
    _write_cp1252(tmp_path / "q.sql", "SELECT 'café';\n")

    assert sql_pdf.create_pdf_from_sql(tmp_path / "q.sql", tmp_path / "q.pdf") is True

    text = "".join(page.extract_text() for page in PdfReader(tmp_path / "q.pdf").pages)
    assert "café" in text


def test_r_rmd_reads_a_windows_1252_file(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    _write_cp1252(input_dir / "analysis.R", "x <- 'café'\n")

    assert R_Rmd.convert_r_to_rmd("analysis.R", None, input_dir, output_dir) is True

    assert "x <- 'café'" in (output_dir / "analysis.Rmd").read_text(encoding="utf-8")


def test_r_rmd_output_has_no_carriage_returns_from_a_windows_file(work_dirs: WorkDirs) -> None:
    """The file used to be opened in text mode, which turns \\r\\n into \\n. That stays."""
    input_dir, output_dir = work_dirs
    (input_dir / "analysis.R").write_bytes(b"x <- 1\r\ny <- 2\r\n")

    assert R_Rmd.convert_r_to_rmd("analysis.R", None, input_dir, output_dir) is True

    assert "\r" not in (output_dir / "analysis.Rmd").read_bytes().decode("utf-8")


def test_md_toon_reads_a_windows_1252_file(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    _write_cp1252(input_dir / "data.md", "| name |\n|---|\n| café |\n")

    summary = md_toon.convert_markdown_to_toon(input_dir, output_dir)

    assert summary.startswith("Converted"), summary
    assert "café" in (output_dir / "data.toon").read_text(encoding="utf-8")


def test_md_pdf_reads_a_windows_1252_file(
    work_dirs: WorkDirs, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only the reading is under test, so pandoc is stood in for by a stub that records
    the Markdown it was handed."""
    input_dir, output_dir = work_dirs
    _write_cp1252(input_dir / "notes.md", "# café\n")
    handed: list[str] = []

    def fake_pandoc(rich_md: str, safe_md: str, output: Path, name: str) -> bool:
        handed.append(safe_md)
        return True

    monkeypatch.setattr(md_pdf, "which", lambda tool: f"/usr/bin/{tool}")
    monkeypatch.setattr(md_pdf, "run_pandoc", fake_pandoc)

    assert md_pdf.convert_md_to_pdf("notes.md", None, input_dir, output_dir) is True
    assert handed and "café" in handed[0]


@needs_rmd_to_pdf
def test_rmd_pdf_reads_a_windows_1252_file(work_dirs: WorkDirs) -> None:
    """Both routes into this converter read the file the same way, so a Windows-1252 file
    used to fail the rmarkdown render and the pandoc fallback, leaving no way through."""
    input_dir, output_dir = work_dirs
    _write_cp1252(input_dir / "doc.Rmd", "---\ntitle: Café\n---\n\nTexte: naïve résumé\n")

    assert Rmd_pdf.convert_rmd_to_pdf("doc.Rmd", None, input_dir, output_dir) is True

    text = "".join(page.extract_text() for page in PdfReader(output_dir / "doc.pdf").pages)
    assert "Café" in text
    assert "naïve résumé" in text
