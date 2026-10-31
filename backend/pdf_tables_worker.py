"""Print the tables PyMuPDF finds in a PDF as JSON, for pdf_toon.

Run it as its own process (`python pdf_tables_worker.py file.pdf`), so the table reader never
sees a PyMuPDF setting that another module changed. pdf_md imports pymupdf4llm, which turns
unset_quad_corrections on for the whole server process, and with it on a cell of `-38%` is
read as `38%\\n-`. The JSON is a list of pages, each a list of tables, each a list of rows.
"""

import contextlib
import json
import sys

import fitz


def read_tables(pdf_file: str) -> list[list[list[list[str | None]]]]:
    """The cells of every table on every page of the PDF, as PyMuPDF reads them."""
    with fitz.open(pdf_file) as doc:
        return [[table.extract() for table in page.find_tables().tables] for page in doc]


if __name__ == "__main__":
    # PyMuPDF prints advice to stdout, which would end up inside the JSON.
    with contextlib.redirect_stdout(sys.stderr):
        pages = read_tables(sys.argv[1])
    json.dump(pages, sys.stdout)
