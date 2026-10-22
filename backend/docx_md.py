"""Convert Word (.docx) documents in input/ to Markdown in output/ via pandoc.

Images are saved to output/<name>_images/ and linked from the Markdown with relative paths.
"""

import subprocess
from pathlib import Path
from shutil import which

from batch_convert import INPUT_DIR, OUTPUT_DIR, convert_files


def _run_pandoc(source: Path, dest: Path) -> None:
    # Runs from inside the output folder with a relative --extract-media path, because
    # pandoc writes image links exactly as given. An absolute path would break the
    # links as soon as the output is moved or zipped.
    result = subprocess.run(
        [
            "pandoc", str(source.resolve()),
            "--to=gfm",                             # GitHub Markdown, pipe tables
            "--wrap=none",                          # no hard line breaks at 72 columns
            f"--extract-media={dest.stem}_images",
            "-o", dest.name,
        ],
        cwd=dest.parent,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "unknown pandoc error")


def convert_docx_to_markdown(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all DOCX files in the input folder to Markdown files in the output folder.

    Uses pandoc, so headings, lists, tables, links, and images carry over. Requires
    pandoc to be installed.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    if not which("pandoc"):
        return "Error: pandoc not found. Install it with: brew install pandoc"

    return convert_files(
        input_dir, output_dir, ('.docx',), ('.md',), _run_pandoc, target_label="markdown"
    )


if __name__ == "__main__":
    result = convert_docx_to_markdown()
    if not result.startswith("Converted"):
        print(result)
