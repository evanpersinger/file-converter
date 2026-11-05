"""Find the external programs and fonts the converters need on macOS, Linux and Windows,
and say how to install the missing ones on the machine this runs on.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

_MAC_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# Checked in order. Names are looked up on PATH, paths are checked as they are.
_CHROME_CANDIDATES = (
    _MAC_CHROME,
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "chrome",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Google\Chrome\Application\chrome.exe"),
)

LIBREOFFICE_CANDIDATES = (
    "libreoffice",
    "soffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
)

# Monospace fonts with Greek, sub/superscripts and math symbols, best first. The default
# LaTeX mono font has none of them, so code blocks would print "?" for them.
_MONO_FONTS = ("Menlo", "DejaVu Sans Mono", "Consolas", "Liberation Mono", "Noto Sans Mono")


def _resolve(candidate: str) -> str | None:
    """The full path of a program name on PATH, or of an existing file path, else None."""
    if os.sep in candidate or "/" in candidate:
        return candidate if Path(candidate).is_file() else None
    return shutil.which(candidate)


def find_chrome() -> str | None:
    """Google Chrome or Chromium, or None when neither is installed. CHROME_PATH in the
    environment wins when it is set."""
    override = os.environ.get("CHROME_PATH")
    if override:
        return override
    for candidate in _CHROME_CANDIDATES:
        found = _resolve(candidate)
        if found:
            return found
    return None


def find_libreoffice_path() -> str | None:
    """The LibreOffice program, without running it, or None when it is not installed."""
    for candidate in LIBREOFFICE_CANDIDATES:
        found = _resolve(candidate)
        if found:
            return found
    return None


def _installed_font_families() -> set[str] | None:
    """Font family names fontconfig knows, or None when fc-list is not there to ask."""
    if not shutil.which("fc-list"):
        return None
    try:
        listing = subprocess.run(
            ["fc-list", ":", "family"], capture_output=True, text=True, timeout=30,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return {name.strip() for line in listing.splitlines() for name in line.split(",")}


def mono_font() -> str | None:
    """A monospace font for LaTeX code blocks that is installed here, or None to keep
    LaTeX's default. Without fc-list to ask (macOS without fontconfig), Menlo on macOS."""
    families = _installed_font_families()
    if families is None:
        return "Menlo" if sys.platform == "darwin" else None
    return next((font for font in _MONO_FONTS if font in families), None)


_HINTS = {
    "darwin": {
        "tesseract": "brew install tesseract",
        "pandoc": "brew install pandoc",
        "latex": "brew install --cask mactex",
        "libreoffice": "brew install --cask libreoffice",
        "chrome": "brew install --cask google-chrome",
        "wkhtmltopdf": "brew install wkhtmltopdf",
    },
    "linux": {
        "tesseract": "sudo apt install tesseract-ocr (or your distro's package)",
        "pandoc": "sudo apt install pandoc (or your distro's package)",
        "latex": "sudo apt install texlive-xetex (or your distro's package)",
        "libreoffice": "sudo apt install libreoffice (or your distro's package)",
        "chrome": "install Google Chrome or Chromium, or set CHROME_PATH",
        "wkhtmltopdf": "sudo apt install wkhtmltopdf (or your distro's package)",
    },
    "win32": {
        "tesseract": "winget install UB-Mannheim.TesseractOCR",
        "pandoc": "winget install JohnMacFarlane.Pandoc",
        "latex": "winget install MiKTeX.MiKTeX",
        "libreoffice": "winget install TheDocumentFoundation.LibreOffice",
        "chrome": "winget install Google.Chrome, or set CHROME_PATH",
        "wkhtmltopdf": "winget install wkhtmltopdf.wkhtmltox",
    },
}


def install_hint(tool: str, platform: str | None = None) -> str:
    """How to install a tool on this OS (or on `platform`, a sys.platform value)."""
    platform = platform or sys.platform
    key = "linux" if platform.startswith("linux") else platform
    return _HINTS.get(key, _HINTS["linux"])[tool]
