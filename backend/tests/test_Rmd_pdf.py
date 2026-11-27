"""Tests for Rmd_pdf.py, which renders an Rmd to PDF with R's rmarkdown.

It has its own loop rather than convert_files: it returns True or False and prints. Only
the early exits and a failed render are tested, because a real render needs the rmarkdown
R package.
"""

import subprocess
from pathlib import Path

import pytest

import Rmd_pdf

WorkDirs = tuple[Path, Path]


def test_a_pdf_path_is_refused(
    work_dirs: WorkDirs, capsys: pytest.CaptureFixture[str]
) -> None:
    input_dir, output_dir = work_dirs

    assert Rmd_pdf.convert_rmd_to_pdf("doc.pdf", None, input_dir, output_dir) is False
    assert "already in pdf format" in capsys.readouterr().out


def test_a_missing_file_gives_false(
    work_dirs: WorkDirs, capsys: pytest.CaptureFixture[str]
) -> None:
    input_dir, output_dir = work_dirs

    assert Rmd_pdf.convert_rmd_to_pdf("ghost.Rmd", None, input_dir, output_dir) is False
    assert "not found" in capsys.readouterr().out


def test_a_failed_render_gives_false_and_shows_rs_error(
    work_dirs: WorkDirs, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "doc.Rmd").write_text("Text.\n", encoding="utf-8")

    def fake_run_tool(cmd: list[str]) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(cmd, 1, "", "object 'x' not found")

    monkeypatch.setattr(Rmd_pdf, "which", lambda tool: f"/usr/bin/{tool}")
    monkeypatch.setattr(Rmd_pdf, "run_tool", fake_run_tool)

    assert Rmd_pdf.convert_rmd_to_pdf("doc.Rmd", None, input_dir, output_dir) is False
    assert "object 'x' not found" in capsys.readouterr().out
