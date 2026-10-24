"""Tests for csv_md.py, which writes each CSV as a pipe-delimited Markdown table."""

from pathlib import Path

import pytest

import csv_md

WorkDirs = tuple[Path, Path]


@pytest.mark.parametrize("filename", ["data.csv", "data.CSV"])
def test_a_csv_becomes_a_markdown_table(work_dirs: WorkDirs, filename: str) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / filename).write_text("name,age\nAda,36\nGrace,45\n", encoding="utf-8")

    summary = csv_md.convert_csv_to_markdown(input_dir, output_dir)

    assert "data.md" in summary
    assert (output_dir / "data.md").read_text(encoding="utf-8") == (
        "| name | age |\n| --- | --- |\n| Ada | 36 |\n| Grace | 45 |\n"
    )


def test_a_header_only_csv_gives_the_header_and_separator(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "data.csv").write_text("name,age\n", encoding="utf-8")

    csv_md.convert_csv_to_markdown(input_dir, output_dir)

    assert (output_dir / "data.md").read_text(encoding="utf-8") == (
        "| name | age |\n| --- | --- |\n"
    )


def test_a_quoted_comma_stays_in_one_cell(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "data.csv").write_text('name,age\n"Lovelace, Ada",36\n', encoding="utf-8")

    csv_md.convert_csv_to_markdown(input_dir, output_dir)

    assert "| Lovelace, Ada | 36 |" in (output_dir / "data.md").read_text(encoding="utf-8")
