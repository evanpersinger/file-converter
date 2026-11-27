"""Convert Word (.docx) documents to PDF.

For each .docx in input/, a headless LibreOffice renders it to a PDF in output/.
"""

from pathlib import Path

from batch_convert import INPUT_DIR, OUTPUT_DIR
from pptx_pdf import convert_with_libreoffice

# Without a named reader, LibreOffice opens a junk file called .docx as plain text and
# "converts" it into a PDF of garbage.
WORD_READER = "--infilter=MS Word 2007 XML"


def convert_docx_to_pdf(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all DOCX files in the input folder to PDF files in the output folder.

    Requires LibreOffice to be installed.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_with_libreoffice(input_dir, output_dir, (".docx",), (WORD_READER,))


if __name__ == "__main__":
    result = convert_docx_to_pdf()
    if not result.startswith("Converted"):
        print(result)
