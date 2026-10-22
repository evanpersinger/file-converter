"""Tests for pdf_toon.py.

The batch contract is the same shape as the other converters. What is specific here is
reading tables back out of a PDF: the PDFs are drawn in each test (with toon_pdf, or with
reportlab for layouts toon_pdf does not make), so there are no binary fixtures.
"""

from pathlib import Path

import fitz
import toon_format
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import PageBreak, SimpleDocTemplate, Table, TableStyle

import pdf_toon
import toon_pdf

WorkDirs = tuple[Path, Path]


def pdf_from_toon(work_dirs: WorkDirs, toon_text: str, name: str = "data.pdf") -> None:
    """Draw a TOON file as a PDF into the input folder, with toon_pdf."""
    input_dir, _ = work_dirs
    source = input_dir.parent / "source"
    source.mkdir(exist_ok=True)
    (source / "data.toon").write_text(toon_text, encoding="utf-8")

    summary = toon_pdf.convert_toon_to_pdf(source, input_dir)

    assert summary.startswith("Converted"), summary
    (input_dir / "data.pdf").rename(input_dir / name)


def pdf_from_tables(path: Path, tables: list[list[list[str]]]) -> None:
    """Draw each table (rows of text, header first) on its own page, ruled with lines."""
    story = []
    for number, rows in enumerate(tables):
        if number:
            story.append(PageBreak())
        table = Table(rows)
        table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
        story.append(table)
    SimpleDocTemplate(str(path), pagesize=letter).build(story)


def convert(work_dirs: WorkDirs) -> str:
    """Convert data.pdf in the input folder and return the TOON text that was written."""
    input_dir, output_dir = work_dirs

    summary = pdf_toon.convert_pdf_to_toon(input_dir, output_dir)

    assert summary.startswith("Converted"), summary
    return (output_dir / "data.toon").read_text(encoding="utf-8")


def failure(work_dirs: WorkDirs) -> str:
    """Convert data.pdf, which should fail, and return the summary."""
    input_dir, output_dir = work_dirs

    summary = pdf_toon.convert_pdf_to_toon(input_dir, output_dir)

    assert summary.startswith("No files converted. 1 failed:")
    assert not (output_dir / "data.toon").exists()
    return summary


# Batch contract


def test_reports_when_input_is_empty(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    assert (
        pdf_toon.convert_pdf_to_toon(input_dir, output_dir)
        == "No PDF files found in input folder"
    )


def test_reports_when_the_file_is_already_toon(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "data.toon").write_text("a: 1\n", encoding="utf-8")

    assert (
        pdf_toon.convert_pdf_to_toon(input_dir, output_dir)
        == "That file is already in TOON format"
    )


def test_converts_several_pdfs(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    pdf_from_tables(input_dir / "one.pdf", [[["a", "b"], ["1", "2"]]])
    pdf_from_tables(input_dir / "two.pdf", [[["c", "d"], ["3", "4"]]])

    summary = pdf_toon.convert_pdf_to_toon(input_dir, output_dir)

    assert "Converted 2 file(s)" in summary
    assert sorted(p.name for p in output_dir.iterdir()) == ["one.toon", "two.toon"]


def test_one_pdf_with_no_table_does_not_stop_the_good_ones(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    pdf_from_tables(input_dir / "good.pdf", [[["a", "b"], ["1", "2"]]])
    pdf_from_toon(work_dirs, "name: Ana\nage: 30\n", name="prose.pdf")

    summary = pdf_toon.convert_pdf_to_toon(input_dir, output_dir)

    assert "good.toon" in summary
    assert "1 failed" in summary
    assert (output_dir / "good.toon").exists()


# Reading tables


def test_a_table_is_read_back_as_a_list_of_objects(work_dirs: WorkDirs) -> None:
    pdf_from_toon(work_dirs, "users[2]{id,name}:\n  1,Ana\n  2,Bo\n")

    assert convert(work_dirs) == "[2]{id,name}:\n  1,Ana\n  2,Bo\n"


def test_values_survive_toon_to_pdf_and_back(work_dirs: WorkDirs) -> None:
    rows = [
        {"n": 1, "f": 1.5, "ok": True, "gone": None, "code": "007", "name": "Ana"},
        {"n": 2, "f": 2.25, "ok": False, "gone": None, "code": "042", "name": "Bo Li"},
    ]
    pdf_from_toon(work_dirs, toon_format.dumps({"rows": rows}) + "\n")

    assert toon_format.loads(convert(work_dirs)) == rows


def test_a_cell_that_wraps_onto_several_lines_is_read_as_one_line(work_dirs: WorkDirs) -> None:
    long_text = " ".join(["words"] * 40)
    pdf_from_toon(work_dirs, f"rows[1]{{id,text}}:\n  1,{long_text}\n")

    assert toon_format.loads(convert(work_dirs)) == [{"id": 1, "text": long_text}]


def test_a_table_that_runs_over_several_pages_is_one_table(work_dirs: WorkDirs) -> None:
    """toon_pdf repeats the header row on each page, so a long table comes back from the
    PDF as one table per page, which has to be joined up again."""
    rows = [{"id": n, "name": f"Person {n}"} for n in range(1, 151)]
    pdf_from_toon(work_dirs, toon_format.dumps({"people": rows}) + "\n")
    input_dir, _ = work_dirs
    with fitz.open(input_dir / "data.pdf") as doc:
        assert doc.page_count > 1

    assert toon_format.loads(convert(work_dirs)) == rows


def test_two_tables_are_named_by_position(work_dirs: WorkDirs) -> None:
    pdf_from_toon(work_dirs, "a[1]{x,y}:\n  1,2\nb[1]{z,w}:\n  3,4\n")

    assert toon_format.loads(convert(work_dirs)) == {
        "table_1": [{"x": 1, "y": 2}],
        "table_2": [{"z": 3, "w": 4}],
    }


def test_tables_on_different_pages_with_different_headers_stay_separate(
    work_dirs: WorkDirs,
) -> None:
    input_dir, _ = work_dirs
    pdf_from_tables(input_dir / "data.pdf", [[["a", "b"], ["1", "2"]], [["c", "d"], ["3", "4"]]])

    assert toon_format.loads(convert(work_dirs)) == {
        "table_1": [{"a": 1, "b": 2}],
        "table_2": [{"c": 3, "d": 4}],
    }


def test_a_table_is_only_joined_to_the_one_on_the_page_right_before(
    work_dirs: WorkDirs,
) -> None:
    """The third page repeats the first page's header, but a different table sits between
    them, so it is not the rest of the first table."""
    input_dir, _ = work_dirs
    same_header = [["a", "b"], ["1", "2"]]
    pdf_from_tables(input_dir / "data.pdf", [same_header, [["x", "y"], ["9", "8"]], same_header])

    assert list(toon_format.loads(convert(work_dirs))) == ["table_1", "table_2", "table_3"]


# PDFs that cannot be read


def test_a_pdf_with_no_ruled_table_fails_with_a_clear_reason(work_dirs: WorkDirs) -> None:
    pdf_from_toon(work_dirs, "name: Ana\nage: 30\n")

    assert "no tables found" in failure(work_dirs)


def test_a_table_with_one_column_is_not_found(work_dirs: WorkDirs) -> None:
    """PyMuPDF does not detect a one-column table, however many rows it has."""
    input_dir, _ = work_dirs
    pdf_from_tables(input_dir / "data.pdf", [[["a"], ["1"], ["2"], ["3"]]])

    assert "no tables found" in failure(work_dirs)


def test_a_blank_pdf_fails_with_a_clear_reason(work_dirs: WorkDirs) -> None:
    input_dir, _ = work_dirs
    with fitz.open() as doc:
        doc.new_page()
        doc.save(input_dir / "data.pdf")

    assert "no tables found" in failure(work_dirs)


def test_a_password_protected_pdf_fails_with_a_clear_reason(work_dirs: WorkDirs) -> None:
    input_dir, _ = work_dirs
    pdf_from_tables(input_dir / "plain.pdf", [[["a"], ["1"]]])
    with fitz.open(input_dir / "plain.pdf") as doc:
        doc.save(input_dir / "data.pdf", encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="secret")
    (input_dir / "plain.pdf").unlink()

    assert "password protected" in failure(work_dirs)


def test_a_file_that_is_not_a_pdf_is_reported_rather_than_raised(work_dirs: WorkDirs) -> None:
    input_dir, _ = work_dirs
    (input_dir / "data.pdf").write_bytes(b"this is not a pdf")

    failure(work_dirs)


def test_a_blank_cell_among_numbers_is_null(work_dirs: WorkDirs) -> None:
    """A cell with no text in a ruled table has no text for PyMuPDF to return, and must not
    crash the read."""
    input_dir, _ = work_dirs
    pdf_from_tables(input_dir / "data.pdf", [[["a", "b"], ["1", "2"], ["3", ""]]])

    assert toon_format.loads(convert(work_dirs)) == [{"a": 1, "b": 2}, {"a": 3, "b": None}]
