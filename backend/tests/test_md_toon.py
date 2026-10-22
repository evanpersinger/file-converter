"""Tests for md_toon.py.

The batch contract is the same shape as the other converters. What is specific here is what
counts as data: only tables are read, each keyed by the heading above it, cells lose their
Markdown formatting, and the output round-trips with toon_md.
"""

from pathlib import Path

import pytest
import toon_format

import md_toon
import toon_md

WorkDirs = tuple[Path, Path]


def convert(work_dirs: WorkDirs, markdown: str) -> str:
    """Convert one Markdown file and return the TOON text that was written."""
    input_dir, output_dir = work_dirs
    (input_dir / "data.md").write_text(markdown, encoding="utf-8")

    summary = md_toon.convert_markdown_to_toon(input_dir, output_dir)

    assert summary.startswith("Converted"), summary
    return (output_dir / "data.toon").read_text(encoding="utf-8")


def failure(work_dirs: WorkDirs, markdown: str) -> str:
    """Convert one Markdown file that should fail and return the summary."""
    input_dir, output_dir = work_dirs
    (input_dir / "data.md").write_text(markdown, encoding="utf-8")

    summary = md_toon.convert_markdown_to_toon(input_dir, output_dir)

    assert summary.startswith("No files converted. 1 failed:")
    assert not (output_dir / "data.toon").exists()
    return summary


# Batch contract


def test_reports_when_input_is_empty(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    assert (
        md_toon.convert_markdown_to_toon(input_dir, output_dir)
        == "No Markdown files found in input folder"
    )


def test_reports_when_the_file_is_already_toon(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "data.toon").write_text("a: 1\n", encoding="utf-8")

    assert (
        md_toon.convert_markdown_to_toon(input_dir, output_dir)
        == "That file is already in TOON format"
    )


def test_converts_several_markdown_files(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "one.md").write_text("| a |\n| - |\n| 1 |\n", encoding="utf-8")
    (input_dir / "two.md").write_text("| b |\n| - |\n| 2 |\n", encoding="utf-8")

    summary = md_toon.convert_markdown_to_toon(input_dir, output_dir)

    assert "Converted 2 file(s)" in summary
    assert sorted(p.name for p in output_dir.iterdir()) == ["one.toon", "two.toon"]


def test_one_file_with_no_table_does_not_stop_the_good_ones(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "good.md").write_text("| a |\n| - |\n| 1 |\n", encoding="utf-8")
    (input_dir / "prose.md").write_text("just words\n", encoding="utf-8")

    summary = md_toon.convert_markdown_to_toon(input_dir, output_dir)

    assert "good.toon" in summary
    assert "1 failed" in summary
    assert (output_dir / "good.toon").exists()


def test_a_file_with_no_table_fails_with_a_clear_reason(work_dirs: WorkDirs) -> None:
    assert "no tables found" in failure(work_dirs, "# Title\n\nSome prose.\n")


def test_an_empty_file_fails_with_a_clear_reason(work_dirs: WorkDirs) -> None:
    assert "no tables found" in failure(work_dirs, "")


def test_a_markdown_file_with_a_byte_order_mark_is_read(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "bom.md").write_bytes(b"\xef\xbb\xbf" + b"| a |\n| - |\n| 1 |\n")

    md_toon.convert_markdown_to_toon(input_dir, output_dir)

    assert (output_dir / "bom.toon").read_text(encoding="utf-8") == "[1]{a}:\n  1\n"


# What counts as data


def test_a_table_under_a_heading_is_keyed_by_it(work_dirs: WorkDirs) -> None:
    toon = convert(work_dirs, "# users\n\n| id | name |\n| --- | --- |\n| 1 | Ana |\n| 2 | Bo |\n")

    assert toon == "users[2]{id,name}:\n  1,Ana\n  2,Bo\n"


def test_a_lone_table_with_no_heading_is_a_list(work_dirs: WorkDirs) -> None:
    toon = convert(work_dirs, "| x | y |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |\n")

    assert toon == "[2]{x,y}:\n  1,2\n  3,4\n"


def test_each_table_is_keyed_by_the_heading_above_it(work_dirs: WorkDirs) -> None:
    toon = convert(
        work_dirs,
        "# first\n\n| a |\n| - |\n| 1 |\n\ntext in between\n\n## second\n\n| b |\n| - |\n| 2 |\n",
    )

    assert toon_format.loads(toon) == {"first": [{"a": 1}], "second": [{"b": 2}]}


def test_text_outside_the_tables_is_left_out(work_dirs: WorkDirs) -> None:
    toon = convert(work_dirs, "Intro paragraph.\n\n- a bullet\n\n| a |\n| - |\n| 1 |\n\nOutro.\n")

    assert toon == "[1]{a}:\n  1\n"


def test_a_table_inside_a_code_block_is_not_read(work_dirs: WorkDirs) -> None:
    markdown = "```\n| a |\n| - |\n| 1 |\n```\n\n| real |\n| - |\n| 2 |\n"

    assert convert(work_dirs, markdown) == "[1]{real}:\n  2\n"


def test_alignment_colons_in_the_header_rule_are_accepted(work_dirs: WorkDirs) -> None:
    assert convert(work_dirs, "| x | y |\n|:---|---:|\n| 1 | 2 |\n") == "[1]{x,y}:\n  1,2\n"


# Cells


def test_formatting_in_a_cell_is_dropped(work_dirs: WorkDirs) -> None:
    markdown = "| a |\n| - |\n| **bold** |\n| *it* |\n| `code` |\n| [text](http://x.y) |\n"

    data = toon_format.loads(convert(work_dirs, markdown))

    assert [row["a"] for row in data] == ["bold", "it", "code", "text"]


def test_a_br_tag_is_a_new_line_and_other_html_is_dropped(work_dirs: WorkDirs) -> None:
    data = toon_format.loads(convert(work_dirs, "| a |\n| - |\n| x<br>y |\n| <b>z</b> |\n"))

    assert [row["a"] for row in data] == ["x\ny", "z"]


def test_escaped_characters_in_a_cell_are_read_as_written(work_dirs: WorkDirs) -> None:
    data = toon_format.loads(convert(work_dirs, "| a |\n| - |\n| a\\|b |\n| snake\\_case |\n"))

    assert [row["a"] for row in data] == ["a|b", "snake_case"]


def test_numbers_booleans_and_null_are_typed_and_codes_stay_text(work_dirs: WorkDirs) -> None:
    markdown = (
        "| n | f | b | z | code | price |\n| - | - | - | - | - | - |\n"
        "| 1 | 1.5 | true | null | 007 | 1.50 |\n"
        "| -2 | 2.25 | false | null | 042 | 2.00 |\n"
    )

    data = toon_format.loads(convert(work_dirs, markdown))

    assert data[0] == {"n": 1, "f": 1.5, "b": True, "z": None, "code": "007", "price": "1.50"}
    assert data[1] == {"n": -2, "f": 2.25, "b": False, "z": None, "code": "042", "price": "2.00"}


def test_a_blank_cell_among_numbers_is_null(work_dirs: WorkDirs) -> None:
    data = toon_format.loads(convert(work_dirs, "| n |\n| - |\n| 1 |\n| |\n| 3 |\n"))

    assert [row["n"] for row in data] == [1, None, 3]


# Tables that cannot be read


def test_a_table_with_rows_of_the_wrong_width_fails_instead_of_being_skipped(
    work_dirs: WorkDirs,
) -> None:
    """The parser reads a table only when every row matches the header. Another table in
    the same file must not let this one vanish without a word."""
    markdown = "| a | b |\n| - | - |\n| 1 |\n\n| c |\n| - |\n| 2 |\n"

    assert "could not read it" in failure(work_dirs, markdown)


# Round trip with toon_md


@pytest.mark.parametrize(
    "data",
    [
        pytest.param({"users": [{"id": 1, "name": "Ana"}, {"id": 2, "name": "Bo"}]}, id="table"),
        pytest.param([{"x": 1, "y": 2.5}, {"x": 3, "y": 4.5}], id="top-level-table"),
        pytest.param(
            {"a": [{"v": 1}], "b": [{"w": "x"}]},
            id="two-tables",
        ),
        pytest.param(
            {"rows": [{"text": "a|b"}, {"text": "snake_case"}, {"text": "*star* `tick` [x]"}]},
            id="markdown-characters",
        ),
        pytest.param(
            {"rows": [{"text": "line1\nline2"}, {"text": "<b>not bold</b>"}, {"text": "back\\slash"}]},
            id="newlines-html-and-backslashes",
        ),
        pytest.param({"rows": [{"name": "café 中文"}, {"name": "ñ ü"}]}, id="unicode"),
        pytest.param(
            {"rows": [{"n": 1, "ok": True, "gone": None, "s": "007"}, {"n": 2, "ok": False, "gone": None, "s": "042"}]},
            id="typed-and-text-columns",
        ),
    ],
)
def test_a_table_survives_toon_to_markdown_and_back(work_dirs: WorkDirs, data: object) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "data.toon").write_text(toon_format.dumps(data) + "\n", encoding="utf-8")
    toon_md.convert_toon_to_markdown(input_dir, output_dir)

    markdown = (output_dir / "data.md").read_text(encoding="utf-8")

    assert toon_format.loads(convert(work_dirs, markdown)) == data
