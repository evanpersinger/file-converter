"""Tests for ipynb_pdf.py, which runs `jupyter nbconvert --to pdf` on one notebook.

It has its own loop rather than convert_files: it returns True or False and prints.
nbconvert is faked by patching run_tool, because a real run needs LaTeX packages
(tcolorbox and more) that xelatex alone does not bring.
"""

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

import ipynb_pdf

WorkDirs = tuple[Path, Path]


def fake_nbconvert(
    commands: list[list[str]], returncode: int = 0, stderr: str = ""
) -> Callable[..., subprocess.CompletedProcess]:
    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        commands.append(command)
        return subprocess.CompletedProcess(command, returncode, "", stderr)

    return run


def test_a_pdf_path_is_refused(
    work_dirs: WorkDirs, capsys: pytest.CaptureFixture[str]
) -> None:
    input_dir, output_dir = work_dirs

    assert ipynb_pdf.convert_notebook_to_pdf("doc.pdf", None, input_dir, output_dir) is False
    assert "already in pdf format" in capsys.readouterr().out


def test_a_missing_file_gives_false(
    work_dirs: WorkDirs, capsys: pytest.CaptureFixture[str]
) -> None:
    input_dir, output_dir = work_dirs

    assert ipynb_pdf.convert_notebook_to_pdf("ghost.ipynb", None, input_dir, output_dir) is False
    assert "not found" in capsys.readouterr().out


def test_nbconvert_is_asked_for_a_pdf_in_the_output_folder(
    work_dirs: WorkDirs, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "nb.ipynb").write_text("{}", encoding="utf-8")
    commands: list[list[str]] = []
    monkeypatch.setattr(ipynb_pdf, "run_tool", fake_nbconvert(commands))

    assert ipynb_pdf.convert_notebook_to_pdf("nb.ipynb", None, input_dir, output_dir) is True

    command = commands[0]
    assert command[:4] == ["jupyter", "nbconvert", "--to", "pdf"]
    assert command[command.index("--output") + 1] == "nb.pdf"
    assert command[command.index("--output-dir") + 1] == str(output_dir)
    assert command[-1] == str(input_dir / "nb.ipynb")


def test_a_failed_nbconvert_gives_false_with_its_error(
    work_dirs: WorkDirs, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "nb.ipynb").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        ipynb_pdf, "run_tool", fake_nbconvert([], returncode=1, stderr="xelatex not found")
    )

    assert ipynb_pdf.convert_notebook_to_pdf("nb.ipynb", None, input_dir, output_dir) is False
    assert "Conversion failed: xelatex not found" in capsys.readouterr().out


def test_missing_jupyter_gives_false_with_a_hint(
    work_dirs: WorkDirs, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "nb.ipynb").write_text("{}", encoding="utf-8")

    def no_jupyter(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        raise FileNotFoundError(command[0])

    monkeypatch.setattr(ipynb_pdf, "run_tool", no_jupyter)

    assert ipynb_pdf.convert_notebook_to_pdf("nb.ipynb", None, input_dir, output_dir) is False
    assert "Make sure Jupyter is installed" in capsys.readouterr().out
