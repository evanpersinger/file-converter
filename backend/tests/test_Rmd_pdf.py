"""Tests for Rmd_pdf.py, which fills in Sys.Date() and renders an Rmd to PDF.

It has its own loop rather than convert_files: it returns True or False and prints. Only
the date replacement and the early exits are tested, because a real render needs the
rmarkdown R package or LaTeX packages (microtype and more) that a bare xelatex lacks.
"""

from datetime import date
from pathlib import Path

import pytest

import Rmd_pdf

WorkDirs = tuple[Path, Path]

TODAY = date.today().strftime("%Y-%m-%d")


def test_inline_sys_date_becomes_todays_date() -> None:
    assert Rmd_pdf.replace_sys_date("Run on `r Sys.Date()`.") == f"Run on {TODAY}."


def test_bare_sys_date_becomes_todays_date() -> None:
    assert Rmd_pdf.replace_sys_date('date: "Sys.Date()"') == f'date: "{TODAY}"'


def test_sys_date_with_spaces_inside_the_brackets_is_replaced() -> None:
    assert Rmd_pdf.replace_sys_date("Sys.Date( )") == TODAY


def test_text_without_sys_date_is_unchanged() -> None:
    assert Rmd_pdf.replace_sys_date("Plain text with `r 1 + 1`.") == "Plain text with `r 1 + 1`."


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


def test_pandoc_fallback_uses_a_highlight_flag_old_pandoc_accepts(
    work_dirs: WorkDirs, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--syntax-highlighting only exists in pandoc 3.8+, so 3.1 (Debian/Ubuntu) rejected
    every conversion. --no-highlight works on both."""
    input_dir, output_dir = work_dirs
    (input_dir / "doc.Rmd").write_text("# Title\n\nText.\n", encoding="utf-8")
    commands: list[list[str]] = []

    def fake_run_tool(cmd, *args, **kwargs):
        commands.append(cmd)
        return type("Result", (), {"returncode": 1, "stdout": "", "stderr": "stub"})()

    monkeypatch.setattr(Rmd_pdf, "command_exists", lambda cmd: cmd == "pandoc")
    monkeypatch.setattr(Rmd_pdf, "run_tool", fake_run_tool)

    Rmd_pdf.convert_rmd_to_pdf("doc.Rmd", None, input_dir, output_dir)

    pandoc_cmd = next(cmd for cmd in commands if cmd[0] == "pandoc")
    assert "--no-highlight" in pandoc_cmd
    assert not any(arg.startswith("--syntax-highlighting") for arg in pandoc_cmd)
