"""Convert PDFs in input/ to Word documents in output/, keeping the layout, locally and for free.

Uses pdf2docx. It does no OCR, so scanned pages do not become text.
"""

from pathlib import Path

import fitz  # PyMuPDF

from batch_convert import INPUT_DIR, OUTPUT_DIR, convert_files


def _write_docx(source: Path, dest: Path) -> None:
    # Imported here because pdf2docx sets up logging for the whole process when it loads
    from pdf2docx import Converter

    with fitz.open(source) as doc:
        if doc.needs_pass:
            raise ValueError("PDF is password protected")

    converter = Converter(str(source))
    try:
        # A page it can't read fails the file, instead of going missing from the Word file
        converter.convert(str(dest), ignore_page_error=False)
    finally:
        converter.close()


def convert_pdf_to_docx(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert every PDF in the input folder to a Word document in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_files(input_dir, output_dir, (".pdf",), (".docx",), _write_docx)


if __name__ == "__main__":
    result = convert_pdf_to_docx()
    if not result.startswith("Converted"):
        print(result)
