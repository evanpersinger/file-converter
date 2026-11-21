"""Convert PDFs in input/ to plain text in output/, locally and for free.

Searchable pages use their embedded text, scanned pages go through Tesseract OCR (English only).
"""

from pathlib import Path

import fitz  # PyMuPDF

from batch_convert import INPUT_DIR, OUTPUT_DIR, convert_files
from pdf_md import TEXT_MIN_CHARS, ocr_page


def pdf_to_text(pdf_path: str | Path) -> str:
    """The text of a PDF, one block per page. A page with too little embedded text is OCRed."""
    with fitz.open(pdf_path) as doc:
        # try an empty password, skip if it's really locked
        if doc.is_encrypted and not doc.authenticate(""):
            raise ValueError("PDF is password protected")

        page_count = doc.page_count
        pages = []
        ocr_count = 0
        for page in doc:
            text = page.get_text("text").strip()
            if len(text) < TEXT_MIN_CHARS:
                text = ocr_page(page).strip() or text
                ocr_count += 1
            if text:
                pages.append(text)

    print(f"{page_count} page(s), {ocr_count} read with OCR")
    return "\n\n".join(pages) + "\n"


def _write_text(source: Path, dest: Path) -> None:
    dest.write_text(pdf_to_text(source), encoding="utf-8")


def convert_pdf_to_txt(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert every PDF in the input folder to a plain text file in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_files(input_dir, output_dir, (".pdf",), (".txt",), _write_text)


if __name__ == "__main__":
    result = convert_pdf_to_txt()
    if not result.startswith("Converted"):
        print(result)
