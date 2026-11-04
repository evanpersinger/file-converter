"""Unicode fonts for the reportlab PDF converters (txt_pdf, toon_pdf).

reportlab's built-in fonts (Helvetica, Courier) only cover the Windows-1252 range, so
Cyrillic, Greek or Chinese came out blank (txt_pdf) or failed (toon_pdf). This finds a
Unicode TrueType font already on the machine, registers it, and wraps any run of
characters it lacks in a second, CJK-capable fallback font when one is installed.

Nothing is bundled: if no candidate font exists the built-in fonts are used, as before.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

_WINDOWS_FONTS = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"

# First file that exists and loads wins. (path, index in a .ttc collection)
_CANDIDATES: dict[str, list[tuple[str, int]]] = {
    "sans": [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 0),  # Debian, Ubuntu
        ("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf", 0),  # Fedora
        ("/usr/share/fonts/TTF/DejaVuSans.ttf", 0),  # Arch
        ("/System/Library/Fonts/Supplemental/Arial.ttf", 0),  # macOS
        ("/Library/Fonts/Arial.ttf", 0),
        (str(_WINDOWS_FONTS / "arial.ttf"), 0),
    ],
    "sans_bold": [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0),
        ("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf", 0),
        ("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", 0),
        ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 0),
        ("/Library/Fonts/Arial Bold.ttf", 0),
        (str(_WINDOWS_FONTS / "arialbd.ttf"), 0),
    ],
    "mono": [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 0),
        ("/usr/share/fonts/dejavu-sans-mono-fonts/DejaVuSansMono.ttf", 0),
        ("/usr/share/fonts/TTF/DejaVuSansMono.ttf", 0),
        ("/System/Library/Fonts/Menlo.ttc", 0),  # macOS
        (str(_WINDOWS_FONTS / "consola.ttf"), 0),
    ],
    # Used only for characters the font above lacks, mostly Chinese, Japanese and Korean.
    "fallback": [
        ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", 0),
        ("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf", 0),
        ("/usr/share/fonts/wqy-zenhei/wqy-zenhei.ttc", 0),
        ("/usr/share/fonts/google-droid-sans-fonts/DroidSansFallbackFull.ttf", 0),
        ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 0),  # macOS
        ("/Library/Fonts/Arial Unicode.ttf", 0),
        (str(_WINDOWS_FONTS / "msyh.ttc"), 0),  # Microsoft YaHei
    ],
}

_BUILTIN = {"sans": "Helvetica", "sans_bold": "Helvetica-Bold", "mono": "Courier"}


@dataclass(frozen=True)
class Fonts:
    """Registered font names, plus which characters each one can draw."""

    sans: str
    sans_bold: str
    mono: str
    fallback: str | None
    # Code points per registered TrueType font. Built-in fonts aren't listed: they cover cp1252.
    _coverage: dict[str, frozenset[int]] = field(default_factory=dict, repr=False, compare=False)

    def can_draw(self, font: str, char: str) -> bool:
        if char in "\n\r\t":
            return True
        coverage = self._coverage.get(font)
        if coverage is None:
            try:
                char.encode("cp1252")
                return True
            except UnicodeEncodeError:
                return False
        return ord(char) in coverage

    def font_for(self, font: str, char: str) -> str | None:
        """The font that draws `char`: `font` itself, else the fallback, else None."""
        if self.can_draw(font, char):
            return font
        if self.fallback and self.can_draw(self.fallback, char):
            return self.fallback
        return None

    def undrawable(self, text: str, font: str) -> list[str]:
        """Distinct characters in `text` that neither `font` nor the fallback can draw."""
        missing: dict[str, None] = {}
        for char in text:
            if self.font_for(font, char) is None:
                missing[char] = None
        return list(missing)

    def markup(self, text: str, font: str) -> str:
        """`text` escaped for a reportlab Paragraph, with runs `font` can't draw switched to
        the fallback font. Characters no font has are left as they are (they draw blank)."""
        parts: list[str] = []
        run: list[str] = []
        run_font: str | None = font

        def flush() -> None:
            if not run:
                return
            chunk = escape("".join(run))
            parts.append(chunk if run_font in (font, None) else f'<font name="{run_font}">{chunk}</font>')
            run.clear()

        for char in text:
            char_font = self.font_for(font, char) or font
            if char_font != run_font:
                flush()
                run_font = char_font
            run.append(char)
        flush()
        return "".join(parts)


def _load(role: str) -> tuple[str, frozenset[int]] | None:
    name = f"FC-{role}"
    for path, index in _CANDIDATES[role]:
        if not Path(path).is_file():
            continue
        try:
            font = TTFont(name, path, subfontIndex=index)
        except Exception:
            # Unreadable, or a CFF-outline font reportlab can't embed. Try the next one.
            continue
        pdfmetrics.registerFont(font)
        return name, frozenset(font.face.charToGlyph)
    return None


@lru_cache(maxsize=1)
def fonts() -> Fonts:
    """Find, register and return the fonts. Cached: registration happens once per process."""
    coverage: dict[str, frozenset[int]] = {}
    names: dict[str, str | None] = {}
    for role in ("sans", "sans_bold", "mono", "fallback"):
        loaded = _load(role)
        if loaded:
            names[role], coverage[loaded[0]] = loaded
        else:
            names[role] = _BUILTIN.get(role)

    sans, sans_bold = names["sans"], names["sans_bold"]
    # A Unicode regular face with a built-in bold face would draw <b> text in Helvetica-Bold
    # and lose the non-Latin characters there, so use the regular face for bold instead.
    if sans in coverage and sans_bold not in coverage:
        sans_bold = sans
    # Map <b> in Paragraph markup to the bold face.
    addMapping(sans, 0, 0, sans)
    addMapping(sans, 1, 0, sans_bold)
    addMapping(sans, 0, 1, sans)
    addMapping(sans, 1, 1, sans_bold)
    # The fallback and mono faces have no bold or italic; <b> inside them keeps the face.
    for single in {names["mono"], names["fallback"]} & set(coverage):
        for bold in (0, 1):
            for italic in (0, 1):
                addMapping(single, bold, italic, single)

    return Fonts(
        sans=sans,
        sans_bold=sans_bold,
        mono=names["mono"],
        fallback=names["fallback"],
        _coverage=coverage,
    )
