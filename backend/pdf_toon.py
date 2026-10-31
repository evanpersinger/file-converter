"""Convert the tables in PDF files to TOON.

For each .pdf in input/, writes a .toon file to output/ holding the tables PyMuPDF finds.
Only ruled tables with at least two columns are found, and a PDF with none fails.
"""

import json
import sys
from pathlib import Path

import fitz
import toon_format

from batch_convert import INPUT_DIR, OUTPUT_DIR, convert_files
from external_tool import run_tool
from toon_tables import FoundTable, tables_to_data

# The tables are read in a process of their own, see pdf_tables_worker.py for why.
_WORKER = Path(__file__).resolve().with_name("pdf_tables_worker.py")


def _clean(cell: str | None) -> str:
    """A cell's text with its wrapped lines joined into one."""
    return ' '.join((cell or '').split())


def _read_page_tables(pdf_file) -> list[list[list[list[str | None]]]]:
    """Every page's tables as rows of raw cell text, read by the worker process.

    Raises:
        ValueError: If the worker could not read the PDF.
    """
    result = run_tool([sys.executable, str(_WORKER), str(pdf_file)])
    if result.returncode != 0:
        lines = result.stderr.strip().splitlines()
        raise ValueError(lines[-1] if lines else 'the tables could not be read')
    return json.loads(result.stdout)


def _find_tables(pages: list[list[list[list[str | None]]]]) -> list[FoundTable]:
    """The tables in a PDF, in reading order, with no titles.

    A table that carries on to the next page shows up there as a second table with the
    header row repeated, and is joined back to the first.
    """
    found: list[list[list[str]]] = []
    carried_over = None  # the last table on the previous page, which may continue here
    for page_tables in pages:
        last_on_page = None
        for index, table in enumerate(page_tables):
            rows = [[_clean(cell) for cell in row] for row in table]
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
    found = _find_tables(_read_page_tables(pdf_file))
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
