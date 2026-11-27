"""Convert PDFs in input/ to plain text in output/, locally and for free.

Searchable pages use their embedded text, scanned pages go through Tesseract OCR (English only).
"""

from collections.abc import Callable
from pathlib import Path

import fitz  # PyMuPDF

from batch_convert import INPUT_DIR, OUTPUT_DIR, convert_files
from pdf_md import TEXT_MIN_CHARS, ocr_until_cancelled


def pdf_to_text(pdf_path: str | Path, should_cancel: Callable[[], bool] = lambda: False) -> str:
    """The text of a PDF, one block per page. A page with too little embedded text is OCRed.

    should_cancel is checked before each of those. True stops the OCR, and the string holds
    every page with embedded text plus the scans read by then. Raises RuntimeError if that
    is nothing.
    """
    with fitz.open(pdf_path) as doc:
        # try an empty password, skip if it's really locked
        if doc.is_encrypted and not doc.authenticate(""):
            raise ValueError("PDF is password protected")

        page_count = doc.page_count
        texts = [page.get_text("text").strip() for page in doc]
        scanned = [i for i, text in enumerate(texts) if len(text) < TEXT_MIN_CHARS]
        ocr_count = 0
        for i, raw in ocr_until_cancelled(doc, scanned, should_cancel):
            texts[i] = raw.strip() or texts[i]
            ocr_count += 1

    pages = [text for text in texts if text]
    if should_cancel() and not pages:
        raise RuntimeError("Cancelled")
    print(f"{page_count} page(s), {ocr_count} read with OCR")
    return "\n\n".join(pages) + "\n"


def convert_pdf_to_txt(
    input_dir: str | Path = INPUT_DIR,
    output_dir: str | Path = OUTPUT_DIR,
    should_cancel: Callable[[], bool] = lambda: False,
) -> str:
    """Convert every PDF in the input folder to a plain text file in the output folder.
    should_cancel stops a file between scanned pages, see pdf_to_text.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """

    def write(source: Path, dest: Path) -> None:
        dest.write_text(pdf_to_text(source, should_cancel), encoding="utf-8")

    return convert_files(input_dir, output_dir, (".pdf",), (".txt",), write)


if __name__ == "__main__":
    result = convert_pdf_to_txt()
    if not result.startswith("Converted"):
        print(result)
