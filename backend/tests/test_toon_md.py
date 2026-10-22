"""Tests for toon_md.py.

The batch contract is the same shape as the other converters. What is specific here is the
rendering: a TOON table has to come out as a Markdown table, and values from the data have
to show as written instead of being read as Markdown.
"""

from pathlib import Path

import toon_md

WorkDirs = tuple[Path, Path]


def render(work_dirs: WorkDirs, toon_text: str) -> str:
    """Convert one TOON file and return the Markdown that was written."""
    input_dir, output_dir = work_dirs
    (input_dir / "data.toon").write_text(toon_text, encoding="utf-8")

    toon_md.convert_toon_to_markdown(input_dir, output_dir)

    return (output_dir / "data.md").read_text(encoding="utf-8")


# Batch contract


def test_reports_when_input_is_empty(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    assert (
        toon_md.convert_toon_to_markdown(input_dir, output_dir)
        == "No TOON files found in input folder"
    )


def test_reports_when_the_file_is_already_markdown(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "notes.md").write_text("# hi\n", encoding="utf-8")

    assert (
        toon_md.convert_toon_to_markdown(input_dir, output_dir)
        == "That file is already in markdown format"
    )


def test_converts_several_toon_files(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "one.toon").write_text("a: 1\n", encoding="utf-8")
    (input_dir / "two.toon").write_text("b: 2\n", encoding="utf-8")

    summary = toon_md.convert_toon_to_markdown(input_dir, output_dir)

    assert "Converted 2 file(s)" in summary
    assert sorted(p.name for p in output_dir.iterdir()) == ["one.md", "two.md"]


def test_malformed_toon_is_reported_rather_than_raised(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "broken.toon").write_text("users[2]{id,name}:\n  1,Ana\n", encoding="utf-8")

    summary = toon_md.convert_toon_to_markdown(input_dir, output_dir)

    assert summary.startswith("No files converted. 1 failed:")
    assert not (output_dir / "broken.md").exists()


def test_one_bad_toon_file_does_not_stop_the_good_ones(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "good.toon").write_text("a: 1\n", encoding="utf-8")
    (input_dir / "bad.toon").write_text('key: "unterminated', encoding="utf-8")

    summary = toon_md.convert_toon_to_markdown(input_dir, output_dir)

    assert "good.md" in summary
    assert "1 failed" in summary
    assert (output_dir / "good.md").exists()


# Tables


def test_a_toon_table_becomes_a_markdown_table(work_dirs: WorkDirs) -> None:
    markdown = render(work_dirs, "users[2]{id,name}:\n  1,Ana\n  2,Bo\n")

    assert markdown == (
        "# users\n\n"
        "| id | name |\n"
        "| --- | --- |\n"
        "| 1 | Ana |\n"
        "| 2 | Bo |\n"
    )


def test_a_top_level_table_has_no_heading(work_dirs: WorkDirs) -> None:
    markdown = render(work_dirs, "[2]{x,y}:\n  1,2\n  3,4\n")

    assert markdown == "| x | y |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |\n"


def test_objects_with_the_same_keys_in_another_order_still_make_one_table(
    work_dirs: WorkDirs,
) -> None:
    markdown = render(work_dirs, "items[2]:\n  - a: 1\n    b: 2\n  - b: 4\n    a: 3\n")

    assert "| a | b |" in markdown
    assert "| 3 | 4 |" in markdown


def test_a_pipe_or_newline_in_a_cell_does_not_break_the_table(work_dirs: WorkDirs) -> None:
    markdown = render(work_dirs, 'rows[1]{note}:\n  "a|b\\nc"\n')

    assert markdown.splitlines()[-1] == "| a\\|b<br>c |"


def test_null_and_boolean_cells_are_spelled_out(work_dirs: WorkDirs) -> None:
    markdown = render(work_dirs, "rows[1]{a,b,c}:\n  null,true,1.5\n")

    assert markdown.splitlines()[-1] == "| null | true | 1.5 |"


# Objects and lists


def test_plain_values_become_bullets(work_dirs: WorkDirs) -> None:
    markdown = render(work_dirs, "name: Ana\nage: 30\nactive: true\nnote: null\n")

    assert markdown == (
        "- **name**: Ana\n- **age**: 30\n- **active**: true\n- **note**: null\n"
    )


def test_nested_objects_become_headings_that_get_deeper(work_dirs: WorkDirs) -> None:
    markdown = render(work_dirs, "meta:\n  author:\n    name: Evan\n")

    assert markdown == "# meta\n\n## author\n\n- **name**: Evan\n"


def test_plain_entries_come_before_nested_sections(work_dirs: WorkDirs) -> None:
    """Written after a nested section, a plain entry would read as part of that section."""
    markdown = render(work_dirs, "meta:\n  author:\n    name: Evan\n  version: 2\n")

    assert markdown.index("- **version**: 2") < markdown.index("## author")


def test_headings_stop_getting_deeper_at_level_six(work_dirs: WorkDirs) -> None:
    deep = "".join(f"{'  ' * depth}{key}:\n" for depth, key in enumerate("abcdefg"))
    markdown = render(work_dirs, deep + f"{'  ' * 7}h: 1\n")

    assert "###### g" in markdown
    assert "####### " not in markdown


def test_a_list_of_plain_values_becomes_bullets(work_dirs: WorkDirs) -> None:
    markdown = render(work_dirs, "tags[3]: a,b,c\n")

    assert markdown == "# tags\n\n- a\n- b\n- c\n"


def test_objects_that_do_not_match_become_numbered_items(work_dirs: WorkDirs) -> None:
    markdown = render(work_dirs, "items[2]:\n  - a: 1\n  - b: 2\n")

    assert markdown == (
        "# items\n\n"
        "- Item 1\n  - **a**: 1\n"
        "- Item 2\n  - **b**: 2\n"
    )


def test_a_table_cell_holding_a_list_falls_back_to_bullets(work_dirs: WorkDirs) -> None:
    """A Markdown cell can't hold a list, so these rows are not written as a table."""
    markdown = render(work_dirs, "people[1]:\n  - name: Ana\n    tags[2]: a,b\n")

    assert "|" not in markdown
    assert "- **tags**:\n    - a\n    - b" in markdown


def test_empty_containers_are_written_as_json_spells_them(work_dirs: WorkDirs) -> None:
    markdown = render(work_dirs, "meta:\n  empty:\n  none[0]:\n")

    assert "- **empty**: {}" in markdown
    assert "- **none**: []" in markdown


def test_an_empty_file_becomes_an_empty_object(work_dirs: WorkDirs) -> None:
    assert render(work_dirs, "") == "{}\n"


# Values show as written


def test_markdown_characters_in_values_are_escaped(work_dirs: WorkDirs) -> None:
    markdown = render(work_dirs, 'name: "snake_case *star* `tick` [link] <b>"\n')

    assert markdown == (
        "- **name**: snake\\_case \\*star\\* \\`tick\\` \\[link\\] \\<b\\>\n"
    )


def test_markdown_characters_in_keys_are_escaped(work_dirs: WorkDirs) -> None:
    markdown = render(work_dirs, '"my_key":\n  a: 1\n')

    assert markdown.startswith("# my\\_key\n")


def test_unicode_is_kept_as_written(work_dirs: WorkDirs) -> None:
    assert render(work_dirs, "name: café 中文\n") == "- **name**: café 中文\n"
