"""Tests for pptx_md.py.

The decks are built with python-pptx in each test, so there are no binary fixtures.
"""

from pathlib import Path

from pptx import Presentation
from pptx.util import Inches

import pptx_md

TITLE_ONLY_LAYOUT = 5


def new_slide():
    prs = Presentation()
    return prs, prs.slides.add_slide(prs.slide_layouts[TITLE_ONLY_LAYOUT])


def extract(prs: Presentation, tmp_path: Path) -> str:
    path = tmp_path / "deck.pptx"
    prs.save(path)
    return pptx_md.extract_text_from_pptx(str(path))


def test_titles_and_plain_text_boxes_are_unchanged(tmp_path: Path) -> None:
    prs, slide = new_slide()
    slide.shapes.title.text = "TITLETEXT"
    slide.shapes.add_textbox(Inches(1), Inches(1.5), Inches(3), Inches(1)).text_frame.text = "PLAINBOXTEXT"

    assert extract(prs, tmp_path) == "## Slide 1\nTITLETEXT\nPLAINBOXTEXT\n\n---\n\n"


def add_table(slide, cells: list[list[str]]):
    rows, cols = len(cells), len(cells[0])
    table = slide.shapes.add_table(rows, cols, Inches(1), Inches(3), Inches(4), Inches(1)).table
    for r, row in enumerate(cells):
        for c, text in enumerate(row):
            table.cell(r, c).text = text
    return table


def test_table_becomes_a_markdown_table(tmp_path: Path) -> None:
    prs, slide = new_slide()
    add_table(slide, [["A", "B"], ["C", "D"]])

    assert extract(prs, tmp_path) == "## Slide 1\n\n| A | B |\n| --- | --- |\n| C | D |\n\n\n---\n\n"


def test_text_after_a_table_is_not_glued_to_it(tmp_path: Path) -> None:
    prs, slide = new_slide()
    add_table(slide, [["A", "B"], ["C", "D"]])
    slide.shapes.add_textbox(Inches(1), Inches(5), Inches(3), Inches(1)).text_frame.text = "AFTER"

    assert "| C | D |\n\nAFTER" in extract(prs, tmp_path)


def test_pipes_and_line_breaks_stay_inside_their_cell(tmp_path: Path) -> None:
    prs, slide = new_slide()
    add_table(slide, [["a|b", "one\ntwo"], ["x", "y"]])

    assert "| a\\|b | one two |\n| --- | --- |\n| x | y |" in extract(prs, tmp_path)


def test_merged_cell_keeps_its_text_and_the_column_count(tmp_path: Path) -> None:
    prs, slide = new_slide()
    table = add_table(slide, [["", ""], ["A", "B"]])
    table.cell(0, 0).merge(table.cell(0, 1))
    table.cell(0, 0).text = "MERGED"

    assert "| MERGED |  |\n| --- | --- |\n| A | B |" in extract(prs, tmp_path)


def test_empty_first_row_still_gets_a_header(tmp_path: Path) -> None:
    prs, slide = new_slide()
    add_table(slide, [["", ""], ["A", "B"]])

    assert "|  |  |\n| --- | --- |\n| A | B |" in extract(prs, tmp_path)


def test_text_inside_a_group_is_kept(tmp_path: Path) -> None:
    prs, slide = new_slide()
    group = slide.shapes.add_group_shape()
    group.shapes.add_textbox(Inches(5), Inches(1.5), Inches(3), Inches(1)).text_frame.text = "GROUPTEXT"

    assert "GROUPTEXT" in extract(prs, tmp_path)


def test_text_inside_a_nested_group_is_kept(tmp_path: Path) -> None:
    prs, slide = new_slide()
    outer = slide.shapes.add_group_shape()
    inner = outer.shapes.add_group_shape()
    inner.shapes.add_textbox(Inches(5), Inches(1.5), Inches(3), Inches(1)).text_frame.text = "NESTEDTEXT"

    assert "NESTEDTEXT" in extract(prs, tmp_path)
