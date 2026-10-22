"""Convert the tables in PDF files to TOON.

For each .pdf in input/, writes a .toon file to output/ holding the tables PyMuPDF finds.
Only ruled tables with at least two columns are found, and a PDF with none fails.
"""

from pathlib import Path

import fitz
import toon_format

from batch_convert import INPUT_DIR, OUTPUT_DIR, convert_files
from toon_tables import FoundTable, tables_to_data


def _clean(cell: str | None) -> str:
    """A cell's text with its wrapped lines joined into one."""
    return ' '.join((cell or '').split())


def _find_tables(doc: fitz.Document) -> list[FoundTable]:
    """The tables in a PDF, in reading order, with no titles.

    A table that carries on to the next page shows up there as a second table with the
    header row repeated, and is joined back to the first.
    """
    found: list[list[list[str]]] = []
    carried_over = None  # the last table on the previous page, which may continue here
    for page in doc:
        last_on_page = None
        for index, table in enumerate(page.find_tables().tables):
            rows = [[_clean(cell) for cell in row] for row in table.extract()]
            if index == 0 and carried_over is not None and rows[0] == carried_over[0]:
                carried_over.extend(rows[1:])
                last_on_page = carried_over
            else:
                found.append(rows)
                last_on_page = rows
        carried_over = last_on_page
    return [FoundTable(None, rows) for rows in found]


# convert a pdf file to toon text
# handles conversion logic
def pdf_to_toon(pdf_file):
    """Read a PDF file and return its tables as TOON text

    Raises:
        ValueError: If the PDF is password protected or has no tables.
    """
    with fitz.open(pdf_file) as doc:
        if doc.needs_pass:
            raise ValueError('the PDF is password protected')
        found = _find_tables(doc)
    if not found:
        raise ValueError(
            'no tables found (only tables drawn with ruling lines and at least two '
            'columns are found, and a scanned PDF has none)'
        )
    return toon_format.dumps(tables_to_data(found)) + '\n'


def _write_toon(source: Path, dest: Path) -> None:
    dest.write_text(pdf_to_toon(source), encoding='utf-8')


# convert all pdf files to toon files
# handles file system operations
def convert_pdf_to_toon(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert the tables in all PDF files in the input folder to TOON files in the output
    folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_files(
        input_dir, output_dir, ('.pdf',), ('.toon',), _write_toon, target_label="TOON"
    )


if __name__ == "__main__":
    result = convert_pdf_to_toon()
    if not result.startswith("Converted"):
        print(result)
