"""Convert PowerPoint (.pptx and the older .ppt) files to PDF.

For each .pptx or .ppt in input/, shells out to a headless LibreOffice (soffice) to render
the slides to PDF in output/. Requires LibreOffice to be installed.
"""

import tempfile
from pathlib import Path

from batch_convert import INPUT_DIR, OUTPUT_DIR, convert_files
from external_tool import ToolTimeout, run_tool

LIBREOFFICE_NOT_FOUND = (
    "LibreOffice not found in PATH. On macOS (Homebrew cask): "
    "brew install --cask libreoffice. If already installed via .app, add a "
    "symlink: sudo ln -s /Applications/LibreOffice.app/Contents/MacOS/soffice "
    "/usr/local/bin/soffice"
)


def _find_libreoffice() -> str | None:
    """Resolve the LibreOffice executable across platforms, or None if there isn't one."""
    libreoffice_executables = [
        'libreoffice',  # common on Linux
        'soffice',      # common alias
        '/Applications/LibreOffice.app/Contents/MacOS/soffice'  # macOS app bundle
    ]
    for candidate in libreoffice_executables:
        try:
            check = run_tool([candidate, '--version'])
            if check.returncode == 0 or 'LibreOffice' in check.stdout:
                return candidate
        except (FileNotFoundError, ToolTimeout):
            continue
    return None


def convert_pptx_to_pdf(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all PPTX and PPT files in the input folder to PDF files in the output folder.

    Requires LibreOffice to be installed.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    executable = None

    def find_executable() -> str | None:
        nonlocal executable
        executable = _find_libreoffice()
        if not executable:
            return LIBREOFFICE_NOT_FOUND
        print(f"Using LibreOffice executable: {executable}")
        return None

    # A throwaway profile per call, because two LibreOffice runs sharing the default one
    # collide and one of them fails.
    with tempfile.TemporaryDirectory() as profile_dir:
        profile = Path(profile_dir).as_uri()

        def render(source: Path, dest: Path) -> None:
            # LibreOffice names the PDF after the source, which is what dest is already called.
            result = run_tool(
                [executable, '--headless', f'-env:UserInstallation={profile}',
                 '--convert-to', 'pdf', '--outdir', str(dest.parent), str(source)],
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip())

        return convert_files(
            input_dir, output_dir, ('.pptx', '.ppt'), ('.pdf',), render, precheck=find_executable
        )


if __name__ == "__main__":
    result = convert_pptx_to_pdf()
    if not result.startswith("Converted"):
        print(result)
