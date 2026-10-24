"""Tests for R_Rmd.py, which turns an R script into an R Markdown document.

It has its own loop rather than convert_files: it returns True or False and prints. The
comments sit on line 6 or later because the first few short comments are treated as a
name and ID block, which is not what is under test here.
"""

from pathlib import Path

import pytest

import R_Rmd

WorkDirs = tuple[Path, Path]

FIVE_LINES = (
    "library(dplyr)\n"
    "data <- read.csv('data.csv')\n"
    "head(data)\n"
    "nrow(data)\n"
    "ncol(data)\n"
)


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


def test_a_comment_after_code_becomes_prose_between_two_chunks(work_dirs: WorkDirs) -> None:
    rmd = to_rmd(work_dirs, FIVE_LINES + "# Plot the results\nplot(data$x)\n")

    assert "ncol(data)\n```\n\nPlot the results\n" in rmd
    assert "```{r}\nplot(data$x)\n```" in rmd


def test_a_double_hash_comment_becomes_a_heading(work_dirs: WorkDirs) -> None:
    rmd = to_rmd(work_dirs, FIVE_LINES + "## Results\nplot(data$x)\n")

    assert "\n## Results\n" in rmd


def test_separator_comments_are_dropped(work_dirs: WorkDirs) -> None:
    rmd = to_rmd(work_dirs, FIVE_LINES + "# ==========\nplot(data$x)\n")

    assert "==========" not in rmd


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
