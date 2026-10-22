"""Tests for toon_pdf.py.

The batch contract is the same shape as the other converters. What is specific here is the
drawing: a TOON table has to come out as a real table, values have to be drawn as written
instead of being read as markup, and text the font cannot draw has to fail loudly. The PDFs
are read back with PyMuPDF.
"""

from pathlib import Path

import fitz

import toon_pdf

WorkDirs = tuple[Path, Path]


def render(work_dirs: WorkDirs, toon_text: str) -> fitz.Document:
    """Convert one TOON file and open the PDF that was written."""
    input_dir, output_dir = work_dirs
    (input_dir / "data.toon").write_text(toon_text, encoding="utf-8")

    summary = toon_pdf.convert_toon_to_pdf(input_dir, output_dir)

    assert summary.startswith("Converted"), summary
    return fitz.open(output_dir / "data.pdf")


def text_of(doc: fitz.Document) -> str:
    return "\n".join(page.get_text() for page in doc)


def fonts_of(doc: fitz.Document, text: str) -> set[str]:
    """The fonts of the text spans that contain `text`."""
    return {
        span["font"]
        for page in doc
        for block in page.get_text("dict")["blocks"]
        for line in block.get("lines", [])
        for span in line["spans"]
        if text in span["text"]
    }


# Batch contract


def test_reports_when_input_is_empty(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    assert (
        toon_pdf.convert_toon_to_pdf(input_dir, output_dir)
        == "No TOON files found in input folder"
    )


def test_reports_when_the_file_is_already_a_pdf(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "doc.pdf").write_bytes(b"%PDF-1.4\n")

    assert (
        toon_pdf.convert_toon_to_pdf(input_dir, output_dir)
        == "That file is already in pdf format"
    )


def test_converts_several_toon_files(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "one.toon").write_text("a: 1\n", encoding="utf-8")
    (input_dir / "two.toon").write_text("b: 2\n", encoding="utf-8")

    summary = toon_pdf.convert_toon_to_pdf(input_dir, output_dir)

    assert "Converted 2 file(s)" in summary
    assert sorted(p.name for p in output_dir.iterdir()) == ["one.pdf", "two.pdf"]


def test_malformed_toon_is_reported_rather_than_raised(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "broken.toon").write_text("users[2]{id,name}:\n  1,Ana\n", encoding="utf-8")

    summary = toon_pdf.convert_toon_to_pdf(input_dir, output_dir)

    assert summary.startswith("No files converted. 1 failed:")
    assert not (output_dir / "broken.pdf").exists()


def test_one_bad_toon_file_does_not_stop_the_good_ones(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "good.toon").write_text("a: 1\n", encoding="utf-8")
    (input_dir / "bad.toon").write_text('key: "unterminated', encoding="utf-8")

    summary = toon_pdf.convert_toon_to_pdf(input_dir, output_dir)

    assert "good.pdf" in summary
    assert "1 failed" in summary
    assert (output_dir / "good.pdf").exists()


# Tables


def test_a_toon_table_is_drawn_as_a_table(work_dirs: WorkDirs) -> None:
    doc = render(work_dirs, "users[2]{id,name}:\n  1,Ana\n  2,Bo\n")

    tables = doc[0].find_tables().tables

    assert len(tables) == 1
    assert tables[0].extract() == [["id", "name"], ["1", "Ana"], ["2", "Bo"]]


def test_the_header_row_is_bold(work_dirs: WorkDirs) -> None:
    doc = render(work_dirs, "users[1]{id,name}:\n  1,Ana\n")

    assert fonts_of(doc, "name") == {"Helvetica-Bold"}
    assert fonts_of(doc, "Ana") == {"Helvetica"}


def test_a_long_table_starts_on_the_page_its_heading_is_on(work_dirs: WorkDirs) -> None:
    """A heading must not drag a table that is longer than a page onto a fresh page."""
    rows = "".join(f"  {n},Person {n}\n" for n in range(1, 151))
    doc = render(work_dirs, f"note: hi\npeople[150]{{id,name}}:\n{rows}")

    first_page = doc[0].get_text()

    assert "note: hi" in first_page
    assert "Person 1" in first_page


def test_a_heading_with_little_room_left_moves_to_the_next_page(work_dirs: WorkDirs) -> None:
    """Enough bullets to leave under an inch at the bottom, then a heading."""
    bullets = "".join(f"item{n:02d}: x\n" for n in range(45))
    doc = render(work_dirs, f"{bullets}section:\n  inner: 1\n")

    assert "section" not in doc[0].get_text()
    assert "section" in doc[1].get_text()


def test_a_long_table_repeats_its_header_on_every_page(work_dirs: WorkDirs) -> None:
    rows = "".join(f"  {n},Person {n}\n" for n in range(1, 151))
    doc = render(work_dirs, f"people[150]{{id,name}}:\n{rows}")

    assert doc.page_count > 1
    for page in doc:
        assert "name" in page.get_text()


# Objects and lists


def test_plain_values_are_drawn_as_key_value_bullets(work_dirs: WorkDirs) -> None:
    doc = render(work_dirs, "name: Ana\nage: 30\nactive: true\nnote: null\n")

    text = text_of(doc)
    for line in ("name: Ana", "age: 30", "active: true", "note: null"):
        assert line in text
    assert fonts_of(doc, "name") == {"Helvetica-Bold"}
    assert fonts_of(doc, "Ana") == {"Helvetica"}


def test_nested_objects_get_headings_and_plain_entries_come_first(work_dirs: WorkDirs) -> None:
    doc = render(work_dirs, "meta:\n  author:\n    name: Evan\n  version: 2\n")

    text = text_of(doc)

    assert "meta" in text
    assert text.index("version: 2") < text.index("author")
    assert "name: Evan" in text


def test_objects_that_do_not_match_are_drawn_as_numbered_items(work_dirs: WorkDirs) -> None:
    doc = render(work_dirs, "items[2]:\n  - a: 1\n  - b: 2\n")

    text = text_of(doc)

    assert "Item 1" in text
    assert "Item 2" in text
    assert "b: 2" in text


def test_a_multi_line_value_keeps_its_lines(work_dirs: WorkDirs) -> None:
    doc = render(work_dirs, 'note: "line1\\nline2"\n')

    lines = text_of(doc).split()

    assert "line1" in lines
    assert "line2" in lines


def test_an_empty_file_is_drawn_as_an_empty_object(work_dirs: WorkDirs) -> None:
    assert "{}" in text_of(render(work_dirs, ""))


def test_the_file_name_is_the_pdf_title(work_dirs: WorkDirs) -> None:
    assert render(work_dirs, "a: 1\n").metadata["title"] == "data"


# Values are drawn as written


def test_markup_and_math_in_values_are_drawn_as_text(work_dirs: WorkDirs) -> None:
    """Nothing in the data is read as Paragraph markup, LaTeX or math."""
    doc = render(
        work_dirs,
        'note: "$5 and $10, \\\\input{x}, <b>not bold</b>, &amp; <font size=40>big</font>"\n',
    )

    text = text_of(doc)

    assert "$5 and $10" in text
    assert "<b>not bold</b>" in text
    assert "&amp;" in text
    assert "<font size=40>big</font>" in text
    assert fonts_of(doc, "not bold") == {"Helvetica"}


def test_markup_in_a_key_is_drawn_as_text(work_dirs: WorkDirs) -> None:
    doc = render(work_dirs, '"<b>key</b>": 1\n')

    assert "<b>key</b>: 1" in text_of(doc)


def test_accented_latin_text_is_drawn(work_dirs: WorkDirs) -> None:
    assert "café ñ ü" in text_of(render(work_dirs, "name: café ñ ü\n"))


def test_text_the_font_cannot_draw_fails_instead_of_printing_boxes(
    work_dirs: WorkDirs,
) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "data.toon").write_text("name: 中文\n", encoding="utf-8")

    summary = toon_pdf.convert_toon_to_pdf(input_dir, output_dir)

    assert summary.startswith("No files converted. 1 failed:")
    assert "cannot draw '中文'" in summary
    assert not (output_dir / "data.pdf").exists()
