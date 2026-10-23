"""Convert PDFs in input/ to Markdown in output/, locally and for free.

Searchable pages go through pymupdf4llm, scanned pages through Tesseract OCR (English only).
"""

import os
import re
import shutil
import unicodedata
from collections import Counter
from pathlib import Path

import fitz  # PyMuPDF
import pymupdf4llm
import pytesseract
from PIL import Image
from tqdm import tqdm

from batch_convert import INPUT_DIR, OUTPUT_DIR, convert_files
from external_tool import ocr_text

# Config
OCR_DPI = 300                      # 300 is the OCR sweet spot; 600 is 4x slower for little gain
TEXT_MIN_CHARS = 20                # a page with fewer real chars is treated as scanned -> OCR
TESSERACT_CONFIG = r"--oem 3 --psm 3"  # psm 3 = auto page layout, good for full pages
TESSERACT_LANG = "eng"
ENABLE_MATH = True                 # normalize math notation to unicode
EXTRACT_IMAGES = False             # if True, save embedded images and link them in the markdown
EDGE_LINES = 3                     # page numbers/headers only sit in a page's first/last N non-blank lines
MIN_HEADER_PAGES = 3               # an edge line repeating on this many pages is a running header
SCRIPT_SIZE_RATIO = 0.85           # a span smaller than this share of its line's font size may be a super/subscript
SCRIPT_MIN_SHIFT = 0.15            # ...if its baseline is also moved by this share of the line's font size

# Point pytesseract at the tesseract binary if it's on PATH.
# (Correct attribute is `tesseract_cmd`; the old code set `pytesseract_cmd`, a no-op.)
_tesseract_path = shutil.which("tesseract")
if _tesseract_path:
    pytesseract.pytesseract.tesseract_cmd = _tesseract_path

# Math normalization
SUPERSCRIPT_MAP = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵",
    "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹", "+": "⁺", "-": "⁻",
    "=": "⁼", "(": "⁽", ")": "⁾", "n": "ⁿ", "i": "ⁱ",
}
SUBSCRIPT_MAP = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅",
    "6": "₆", "7": "₇", "8": "₈", "9": "₉", "+": "₊", "-": "₋",
    "=": "₌", "(": "₍", ")": "₎",
    "a": "ₐ", "e": "ₑ", "h": "ₕ", "i": "ᵢ", "j": "ⱼ", "k": "ₖ",
    "l": "ₗ", "m": "ₘ", "n": "ₙ", "o": "ₒ", "p": "ₚ", "r": "ᵣ",
    "s": "ₛ", "t": "ₜ", "u": "ᵤ", "v": "ᵥ", "x": "ₓ",
}

# Backslash-prefixed LaTeX commands are unambiguous, so replacing them is safe.
LATEX_SYMBOLS = {
    # lowercase greek
    r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\delta": "δ",
    r"\epsilon": "ε", r"\varepsilon": "ε", r"\zeta": "ζ", r"\eta": "η",
    r"\theta": "θ", r"\iota": "ι", r"\kappa": "κ", r"\lambda": "λ",
    r"\mu": "μ", r"\nu": "ν", r"\xi": "ξ", r"\pi": "π", r"\rho": "ρ",
    r"\sigma": "σ", r"\tau": "τ", r"\upsilon": "υ", r"\phi": "φ",
    r"\varphi": "φ", r"\chi": "χ", r"\psi": "ψ", r"\omega": "ω",
    # uppercase greek
    r"\Gamma": "Γ", r"\Delta": "Δ", r"\Theta": "Θ", r"\Lambda": "Λ",
    r"\Xi": "Ξ", r"\Pi": "Π", r"\Sigma": "Σ", r"\Phi": "Φ",
    r"\Psi": "Ψ", r"\Omega": "Ω",
    # operators / calculus / logic / set theory
    r"\sum": "∑", r"\prod": "∏", r"\int": "∫", r"\oint": "∮",
    r"\partial": "∂", r"\nabla": "∇", r"\infty": "∞", r"\sqrt": "√",
    r"\pm": "±", r"\mp": "∓", r"\times": "×", r"\div": "÷",
    r"\cdot": "·", r"\ast": "∗", r"\leq": "≤", r"\le": "≤",
    r"\geq": "≥", r"\ge": "≥", r"\neq": "≠", r"\ne": "≠",
    r"\approx": "≈", r"\equiv": "≡", r"\propto": "∝", r"\sim": "∼",
    r"\in": "∈", r"\notin": "∉", r"\subset": "⊂", r"\subseteq": "⊆",
    r"\supset": "⊃", r"\supseteq": "⊇", r"\cup": "∪", r"\cap": "∩",
    r"\emptyset": "∅", r"\forall": "∀", r"\exists": "∃",
    r"\neg": "¬", r"\land": "∧", r"\lor": "∨",
    r"\rightarrow": "→", r"\to": "→", r"\leftarrow": "←",
    r"\Rightarrow": "⇒", r"\Leftarrow": "⇐", r"\leftrightarrow": "↔",
    r"\Leftrightarrow": "⇔", r"\mapsto": "↦",
    r"\degree": "°", r"\angle": "∠", r"\perp": "⊥", r"\parallel": "∥",
}


def _map_chars(s, table, prefix):
    """Map every char in `s` via `table`; if any char is unmappable, keep the
    original `prefix + s` form so nothing is silently lost."""
    out = []
    for ch in s:
        if ch not in table:
            return prefix + s
        out.append(table[ch])
    return "".join(out)


def _to_superscript(s):
    return _map_chars(s, SUPERSCRIPT_MAP, "^")


def _to_subscript(s):
    return _map_chars(s, SUBSCRIPT_MAP, "_")


# Characters allowed immediately before ^ or _ for it to count as an explicit
# superscript/subscript: ASCII identifiers/brackets, a closing brace (so a
# chained x_{i}^{j} keeps converting), and the unicode symbols LATEX_SYMBOLS
# itself just substituted in, since \sigma^2 and \sum_{i=1}^n replace their
# symbol before this check ever runs.
_SCRIPT_BASE_CHARS = "A-Za-z0-9\\)\\]\\}" + re.escape("".join(dict.fromkeys(LATEX_SYMBOLS.values())))


def _apply_math(text, ocr):
    # LaTeX commands (longest first so \varepsilon wins over \epsilon-ish prefixes)
    for cmd in sorted(LATEX_SYMBOLS, key=len, reverse=True):
        text = text.replace(cmd, LATEX_SYMBOLS[cmd])

    # ASCII operators
    text = text.replace("<=", "≤").replace(">=", "≥")
    text = text.replace("!=", "≠").replace("~=", "≈")
    text = text.replace("+/-", "±").replace("-/+", "∓")
    text = re.sub(r"(?<![<>=+\-])->", "→", text)   # arrow, but not part of --> etc.

    # sqrt: join a √ left dangling on its own line, then sqrt( / sqrt<space>
    text = re.sub(r"√\s*\n\s*", "√", text)
    text = re.sub(r"\bsqrt\s*\(", "√(", text)
    text = re.sub(r"\bsqrt\s+", "√", text)

    # explicit superscript: x^2, x^{10}, x^n, x^{-1}
    text = re.sub(
        r"([" + _SCRIPT_BASE_CHARS + r"])\^(\{[^}]+\}|-?\d+|[A-Za-z](?![A-Za-z]))",
        lambda m: m.group(1) + _to_superscript(m.group(2).strip("{}")),
        text,
    )
    # a bare-letter superscript chained right after a closing brace (e.g. the "n" in
    # \sum_{i=1}^nw_i) is an operator bound, not a run-on word, so unlike the general
    # case above, it still converts even when the next character is also a letter.
    text = re.sub(
        r"(?<=\})\^([A-Za-z])",
        lambda m: _to_superscript(m.group(1)),
        text,
    )
    # explicit subscript: x_1, x_i, x_{ij}  (multi-letter only via braces, so snake_case is safe)
    text = re.sub(
        r"([" + _SCRIPT_BASE_CHARS + r"])_(\{[^}]+\}|-?\d+|[A-Za-z](?![A-Za-z]))",
        lambda m: m.group(1) + _to_subscript(m.group(2).strip("{}")),
        text,
    )

    if ocr:
        # OCR often reads a minus sign as an em/en dash. Searchable pages keep their
        # dashes, since in prose and page ranges they are real dashes.
        text = text.replace("—", "-").replace("–", "-")
        # A lone variable letter followed by a single digit at a token boundary
        # (x2 -> x²) but never inside a word (COVID19, GPT4 stay put).
        text = re.sub(
            r"(?<![A-Za-z0-9])([A-Za-z])(\d)(?![A-Za-z0-9])",
            lambda m: m.group(1) + _to_superscript(m.group(2)),
            text,
        )
        # tidy OCR whitespace
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

    return text


# Math fonts store variables as styled letters (U+1D400 block, plus the italic h at
# U+210E), so a typeset PDF yields 𝜎 and 𝑥 where the reader expects σ and x. pymupdf4llm
# writes an exponent as " [2]" after its base, and that only counts as one straight after
# a styled letter: after a word, "[2]" is more likely a citation.
_MATH_STYLED_LETTER = re.compile(r"([\U0001d400-\U0001d7ffℎ])(?: ?\[(\d+)\])?")


def _plain_math_letter(match):
    letter = unicodedata.normalize("NFKC", match.group(1))
    return letter + _to_superscript(match.group(2)) if match.group(2) else letter


def normalize_math(text, ocr=False):
    """Normalize math notation, leaving code spans and LaTeX math intact.

    Code spans/blocks are protected untouched. LaTeX math delimiters are
    normalized to markdown's `$..$` / `$$..$$` (\\( \\) -> $ $, \\[ \\] -> $$ $$)
    and their LaTeX contents preserved so a math-aware viewer renders them.
    Any remaining loose notation in plain text is converted to unicode.
    """
    if not ENABLE_MATH or not text:
        return text

    protected = []

    def stash(s):
        protected.append(s)
        return f"\x00{len(protected) - 1}\x00"

    # 1. protect fenced code blocks, then inline code
    text = re.sub(r"```.*?```", lambda m: stash(m.group(0)), text, flags=re.S)
    text = re.sub(r"`[^`\n]*`", lambda m: stash(m.group(0)), text)

    # 2. normalize LaTeX math delimiters to $ / $$ and protect their contents.
    #    \[ \] and \( \) are unambiguous; $$ .. $$ is display math. A single
    #    $ .. $ is only treated as math when it contains \, ^ or _, so that
    #    plain prices like "$5 and $10" are left alone.
    text = re.sub(r"\\\[(.+?)\\\]", lambda m: stash(f"$${m.group(1).strip()}$$"), text, flags=re.S)
    text = re.sub(r"\\\((.+?)\\\)", lambda m: stash(f"${m.group(1).strip()}$"), text, flags=re.S)
    text = re.sub(r"\$\$(.+?)\$\$", lambda m: stash(f"$${m.group(1).strip()}$$"), text, flags=re.S)
    text = re.sub(
        r"\$(?!\$)([^$\n]*?[\\^_][^$\n]*?)\$",
        lambda m: stash(f"${m.group(1).strip()}$"),
        text,
    )

    # 3. convert remaining loose notation in plain text
    text = _MATH_STYLED_LETTER.sub(_plain_math_letter, text)
    text = _apply_math(text, ocr)

    # 4. restore protected spans (loop in case a span nested another)
    for _ in range(5):
        if "\x00" not in text:
            break
        text = re.sub(r"\x00(\d+)\x00", lambda m: protected[int(m.group(1))], text)
    return text


# A page number on its own line: 1-4 digits, optionally a markdown heading or bold (## 3, **3**).
_PAGE_NUMBER = re.compile(r"[#*\s]*[0-9]{1,4}[*\s]*")


def strip_page_numbers(text):
    """Drop page-number lines from the top and bottom of one page's markdown.

    Only the first and last EDGE_LINES non-blank lines are checked, so a digits-only line
    in the middle of a page (a table cell, a list marker) is never touched.
    """
    lines = text.split("\n")
    nonblank = [i for i, line in enumerate(lines) if line.strip()]
    edge = set(nonblank[:EDGE_LINES] + nonblank[-EDGE_LINES:])
    kept = [line for i, line in enumerate(lines) if not (i in edge and _PAGE_NUMBER.fullmatch(line))]
    return "\n".join(kept).strip()


_DIGITS = re.compile(r"[0-9]+")


def _header_key(line):
    """The line with its digits removed, so "58 A. B. Author" and "60 A. B. Author" match.

    Empty for table rows and markdown headings, which are never treated as running headers.
    """
    if line.lstrip().startswith(("|", "#")):
        return ""
    return " ".join(_DIGITS.sub("", line).split())


def strip_repeated_headers(pages):
    """Drop running headers and footers that repeat across pages, keeping the first copy.

    Only the first and last EDGE_LINES non-blank lines of a page are checked. An edge line
    is a running header/footer if, digits aside, it sits at the edge of MIN_HEADER_PAGES or
    more pages. The first page it shows up on keeps it, so details that may appear nowhere
    else (a journal name, a DOI) survive once.
    """
    split = [page.split("\n") for page in pages]
    edges = []
    for lines in split:
        nonblank = [i for i, line in enumerate(lines) if line.strip()]
        edges.append(set(nonblank[:EDGE_LINES] + nonblank[-EDGE_LINES:]))

    page_counts = Counter(
        key
        for lines, edge in zip(split, edges)
        for key in {_header_key(lines[i]) for i in edge}
        if key
    )
    repeated = {key for key, count in page_counts.items() if count >= MIN_HEADER_PAGES}

    seen = set()
    cleaned = []
    for lines, edge in zip(split, edges):
        kept = []
        for i, line in enumerate(lines):
            key = _header_key(line) if i in edge else ""
            if key in repeated:
                if key in seen:
                    continue
                seen.add(key)
            kept.append(line)
        cleaned.append("\n".join(kept).strip())
    return cleaned


def find_scripts(page):
    """List the superscripts and subscripts on a searchable page, in reading order.

    Each is `(before, script, kind)`: the (up to 2) characters just ahead of it, so it can
    be found in the markdown, its text, and "sup" or "sub". A span counts when it is
    smaller than the rest of its line and its baseline is raised or lowered. PyMuPDF's own
    superscript flag is not used, it is set on ordinary spans and missed on real ones.
    Spans stacked over each other (fraction parts, sum bounds) are not scripts, so skipped.
    """
    found = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            spans = line["spans"]
            real = [s for s in spans if s["text"].strip()]
            if not real:
                continue
            full_size = max(s["size"] for s in real)
            small_below = full_size * SCRIPT_SIZE_RATIO
            baselines = Counter(round(s["origin"][1], 1) for s in real if s["size"] >= small_below)
            baseline = baselines.most_common(1)[0][0]

            # index in `spans` -> how far the baseline is raised (positive) or lowered
            shifts = {}
            for i, span in enumerate(spans):
                shift = baseline - span["origin"][1]
                if (span["text"].strip() and span["size"] < small_below
                        and abs(shift) >= full_size * SCRIPT_MIN_SHIFT):
                    shifts[i] = shift

            for i, shift in shifts.items():
                x0, x1 = spans[i]["bbox"][0], spans[i]["bbox"][2]
                stacked = any(
                    shift * other_shift < 0
                    and x0 < spans[j]["bbox"][2] and spans[j]["bbox"][0] < x1
                    for j, other_shift in shifts.items()
                )
                before = "".join(s["text"] for s in spans[:i]).rstrip()[-2:]
                if before and not stacked:
                    found.append((before, spans[i]["text"].strip(), "sup" if shift > 0 else "sub"))
    return found


def apply_scripts(text, scripts):
    """Rewrite the scripts from find_scripts as unicode superscripts and subscripts.

    A script is rewritten at most as many times as the PDF has it, wherever the text puts
    it, so matching does not depend on pymupdf4llm keeping the page's reading order. One
    that is not found (written differently, like `(x][i]`) is left alone. pymupdf4llm
    brackets some scripts (`x [2]`) and writes the rest inline (`x1`); only the bracketed
    form may have a space, or the prose "box 2" would match.
    """
    for (before, script, kind), count in Counter(scripts).items():
        convert = _to_superscript if kind == "sup" else _to_subscript
        pattern = re.escape(before) + r"(?: ?\[" + re.escape(script) + r"\]|" + re.escape(script) + r"(?!\d))"
        text = re.sub(pattern, lambda _: before + convert(script), text, count=count)
    return text


# PDF -> markdown
def _ocr_page(page):
    """Render a page to an image and OCR it."""
    pix = page.get_pixmap(dpi=OCR_DPI)
    mode = "RGBA" if pix.alpha else "RGB"
    img = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
    if mode == "RGBA":
        img = img.convert("RGB")
    return ocr_text(img, config=TESSERACT_CONFIG, lang=TESSERACT_LANG)


def pdf_to_markdown(pdf_path, image_dir=None):
    """Convert a single PDF to a markdown string. image_dir is where extracted images go."""
    doc = fitz.open(pdf_path)
    if doc.is_encrypted:
        # try an empty password; skip if it's really locked
        if not doc.authenticate(""):
            doc.close()
            raise ValueError("PDF is password protected")

    n_pages = doc.page_count

    # Classify each page: enough embedded text -> searchable, else -> OCR.
    text_pages, ocr_pages = [], []
    for i in range(n_pages):
        if len(doc[i].get_text("text").strip()) >= TEXT_MIN_CHARS:
            text_pages.append(i)
        else:
            ocr_pages.append(i)

    md_by_page = {}

    # Searchable pages -> real markdown via pymupdf4llm
    if text_pages:
        md_kwargs = dict(pages=text_pages, page_chunks=True, show_progress=False)
        if EXTRACT_IMAGES and image_dir is not None:
            os.makedirs(image_dir, exist_ok=True)
            md_kwargs.update(write_images=True, image_path=str(image_dir), image_format="png")
        chunks = pymupdf4llm.to_markdown(doc, **md_kwargs)
        texts = strip_repeated_headers([strip_page_numbers(chunk["text"].strip()) for chunk in chunks])
        for page_no, text in zip(text_pages, texts):
            if ENABLE_MATH:
                text = apply_scripts(text, find_scripts(doc[page_no]))
            md_by_page[page_no] = normalize_math(text, ocr=False)

    # Scanned/image pages -> OCR
    if ocr_pages:
        for i in tqdm(ocr_pages, desc=f"OCR {Path(pdf_path).name}", unit="page", leave=False):
            raw = _ocr_page(doc[i])
            md_by_page[i] = normalize_math(raw.strip(), ocr=True)

    doc.close()

    kind = "searchable" if not ocr_pages else ("scanned" if not text_pages else "mixed")
    print(f"{n_pages} page(s): {len(text_pages)} searchable, {len(ocr_pages)} OCR ({kind})")

    parts = [f"<!-- page {i + 1} -->\n\n{md_by_page[i]}" for i in range(n_pages) if md_by_page.get(i)]
    return "\n\n".join(parts).strip() + "\n"


# Runner
def _write_markdown(source: Path, dest: Path) -> None:
    dest.write_text(pdf_to_markdown(str(source), dest.parent / "images"), encoding="utf-8")


def convert_pdf_to_markdown(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert every PDF in the input folder to Markdown in the output folder.

    Searchable pages become real Markdown; scanned pages fall back to OCR, handled
    page by page so mixed PDFs work. This runs locally and is free, unlike the
    LLM-powered versions in llm_pdf_md.py.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_files(input_dir, output_dir, (".pdf",), (".md",), _write_markdown)


def main():
    result = convert_pdf_to_markdown()
    if not result.startswith("Converted"):
        print(result)


if __name__ == "__main__":
    main()
