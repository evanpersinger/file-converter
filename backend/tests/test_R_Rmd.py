"""Tests for R_Rmd.py, which turns an R script into an R Markdown document.

It has its own loop rather than convert_files: it returns True or False and prints.
"""

from pathlib import Path

import pytest

import R_Rmd

WorkDirs = tuple[Path, Path]


def to_rmd(work_dirs: WorkDirs, script: str) -> str:
    """Convert the script as analysis.R and return the text of analysis.Rmd."""
    input_dir, output_dir = work_dirs
    (input_dir / "analysis.R").write_text(script, encoding="utf-8")
    assert R_Rmd.convert_r_to_rmd("analysis.R", None, input_dir, output_dir) is True
    return (output_dir / "analysis.Rmd").read_text(encoding="utf-8")


def test_the_document_starts_with_a_yaml_header(work_dirs: WorkDirs) -> None:
    rmd = to_rmd(work_dirs, "x <- 1\n")

    assert rmd.startswith('---\ntitle: "R Analysis"\noutput: pdf_document\n---\n')


def test_code_goes_into_an_r_chunk(work_dirs: WorkDirs) -> None:
    rmd = to_rmd(work_dirs, "x <- c(1, 2, 3)\nmean(x)\n")

    assert "```{r}\nx <- c(1, 2, 3)\nmean(x)\n```" in rmd


def test_a_comment_inside_a_function_stays_in_the_one_chunk(work_dirs: WorkDirs) -> None:
    script = "f <- function(x) {\n  # double it\n  x * 2\n}\n"

    rmd = to_rmd(work_dirs, script)

    assert f"```{{r}}\n{script}```\n" in rmd


def test_the_output_name_gets_rmd_added(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "analysis.R").write_text("x <- 1\n", encoding="utf-8")

    R_Rmd.convert_r_to_rmd("analysis.R", "report", input_dir, output_dir)

    assert (output_dir / "report.Rmd").exists()


def test_an_rmd_path_is_refused(
    work_dirs: WorkDirs, capsys: pytest.CaptureFixture[str]
) -> None:
    input_dir, output_dir = work_dirs

    assert R_Rmd.convert_r_to_rmd("notes.Rmd", None, input_dir, output_dir) is False
    assert "already in Rmd format" in capsys.readouterr().out


def test_a_missing_file_gives_false_and_no_rmd(
    work_dirs: WorkDirs, capsys: pytest.CaptureFixture[str]
) -> None:
    input_dir, output_dir = work_dirs

    assert R_Rmd.convert_r_to_rmd("ghost.R", None, input_dir, output_dir) is False
    assert "not found" in capsys.readouterr().out
    assert list(output_dir.iterdir()) == []


def test_an_existing_rmd_is_overwritten(work_dirs: WorkDirs) -> None:
    _, output_dir = work_dirs
    output_dir.mkdir()
    (output_dir / "analysis.Rmd").write_text("stale", encoding="utf-8")

    rmd = to_rmd(work_dirs, "x <- 1\n")

    assert "stale" not in rmd
    assert "x <- 1" in rmd
