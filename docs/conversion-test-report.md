# Conversion Test Report

Every pair in the server's conversion list (`REGISTRY` in `backend/server.py`) was run through
`POST /api/convert`, using FastAPI's TestClient and generated sample files. Then each output was
checked for missing content. No source code was changed.

- **Commit tested:** `e57b961`
- **Date:** 2026-11-05
- **Scope:** 55 conversions. Counting each source extension separately (`.jpg`/`.jpeg`,
  `.pptx`/`.ppt`, `.html`/`.htm`, five image types for OCR), that makes **79 pairs**.

## Summary

| Result | Pairs |
|---|---|
| Ran and produced output | 66 |
| ...of those, lose content or formatting on the main sample or an edge case (see below) | 16 |
| Could not run here (network policy blocks the Whisper model download) | 1 (`mp4->md`) |
| Not run (LLM routes: no Ollama, no API keys) | 12 |

The 16: `png->pdf`, `pdf->md`, `pptx->md` (.pptx and .ppt), `txt->pdf`, `sql->pdf`,
`docx->pdf`, `md->pdf`, `ipynb->pdf`, `docx->md`, `gif->png`, `img->txt` (gif),
`img->txt-tables` (gif), `csv->md`, `csv->xlsx`, `r->rmd`.

The existing test suite passes in this environment (`uv run pytest`: 1114 passed), so none of
the findings below is covered by a current test. No supported pair crashed the server. Every loss below happens while the converter **reports
success**, so these are good candidates for `CONVERSIONS.md`.

## Findings, worst first

### 1. PNG to PDF: transparent areas turn black (high)

`png->pdf` (`image_convert.save_pdf`) calls `img.convert("RGB")` without flattening onto
white first, so every transparent pixel becomes black. A black logo or black text on a
transparent PNG gives a **solid black page**: the content is completely gone.

- Repro: a 600×200 transparent PNG with black text "BLACK TEXT" became a page where every
  pixel is 0 (black).
- `webp->pdf` and `gif->pdf` use `save_pdf_pages`, which flattens onto white, and are fine.
- `heic->pdf` uses the same `save_pdf`, so a HEIC with an alpha channel will have the same
  problem. (Not tested: the HEIC sample had no alpha.)
- `png->jpg` and `webp->jpg` flatten onto white correctly.

### 2. PDF to Markdown: a paragraph touching a table is dropped (high)

`pdf->md` lost the sentence "The quick brown Quokka jumps over the lazy Narwhal." It sat
right above a ruled table. The heading and the table came through, but the paragraph was
missing entirely.

- This happens inside `pymupdf4llm.to_markdown` (0.3.4), not in the repo's post-processing.
- Narrowed down: a full-width paragraph with **no gap** above a ruled table is dropped.
  With a 24pt gap or more, it survives.
- A related problem in the same test: with a short paragraph, the text was kept but in the
  **wrong order**. The sentence above the table was placed before the page heading, and a
  sentence below the table was placed above it.

### 3. PowerPoint to Markdown: body text collapsed into one heading (high)

`_append_shape_text` in `pptx_md.py` treats a shape as a heading when its first run has an
explicit font size over 200000 EMU (about 15.75pt). It then joins **all** of the shape's
paragraphs into one `###` line.

- `.ppt` input: LibreOffice writes explicit font sizes when it converts .ppt to .pptx, so
  bullets "Quokka bullet" / "Narwhal bullet" came out as `### Quokka bullet Narwhal bullet`.
  The list structure and line breaks are lost.
- Plain `.pptx` is affected too: a body placeholder with 24pt bullets gives
  `### First bullet Second bullet`. Explicit body sizes like that are common in real decks.

### 4. Non-Latin text in text-to-PDF converters (medium)

Test line: `Latin Zebra / 東京タワー / Ελληνικά / Привет / emoji 🎉 / Ocelot`

| Pair | Result |
|---|---|
| `txt->pdf`, `sql->pdf`, `docx->pdf` | CJK, Cyrillic, emoji and accented Greek drawn as black boxes (■). They use ReportLab's built-in Helvetica/Courier. |
| `md->pdf`, `ipynb->pdf` | CJK, Cyrillic and emoji **silently left out** (blank space). In md->pdf, Greek is set in math italic and "ά" is missing. |
| `toon->pdf` | Fails with a clear error. Matches the UI note ("Latin text only"). |
| `html->pdf` (wkhtmltopdf), `html->svg` | All scripts render correctly. |

The fonts involved (ReportLab built-ins, Latin Modern) are the same on macOS, so this is not
just a Linux issue. Only `toon->pdf` warns the user.

### 5. Word to PDF: formatting not carried over (medium)

`docx->pdf` rebuilds the document with ReportLab instead of rendering it:

- The Heading 1 style comes out as plain body text.
- Bullet markers are dropped: list items look like normal paragraphs.
- Page header text ("HeaderWombat") is dropped.
- A "Document: sample" title that isn't in the source is added at the top.
- Text, bold, the table and the image all survive.

### 6. Word to Markdown: header dropped (low)

`docx->md` (pandoc) drops page header and footer text. Everything else came through: heading,
bold, accents, bullets, table, and the image in a zip. Pandoc normally does this, but nothing
tells the user.

### 7. PowerPoint: notes and pictures (low)

- `pptx->md` (.pptx and .ppt): speaker notes are dropped, and pictures on a slide leave no
  trace in the Markdown (no image link or placeholder).
- `pptx->pdf`: notes are not included. LibreOffice normally does this; the slides themselves
  are fine.

### 8. Animated GIFs give only the first frame (low)

- `gif->png`: 1 of 3 frames. This is in the script's docstring but not in the UI note.
- `img->txt` / `img->txt-tables` on a GIF: only frame 1 is OCR'd. Text in frames 2–3 is lost.
- By contrast, `gif->pdf` gives one page per frame and `gif->svg` gives a zip with one SVG
  per frame.

### 9. CSV edge cases (low to medium)

- A **Windows-1252 / Latin-1** CSV (what Excel on Windows often saves) **fails** in both
  `csv->md` and `csv->xlsx` with `'utf-8' codec can't decode byte 0xe9`.
- A **semicolon-delimited** CSV (common in European locales) "succeeds" but comes out as a
  single column (`| name;city |`).

### 10. Smaller formatting losses (low)

- `md->pdf`: em and en dashes become `-` everywhere, code blocks included (deliberate:
  `md_pdf.py:160`). Raw `<angle>` text is dropped, because pandoc reads it as an HTML tag.
- `r->rmd`: R comments become bold text that keeps the comment marker:
  `# Zebra analysis` → `**## Zebra analysis**`, `#' Roxygen…` → `**' Roxygen…**`.
- `md->toon` and `pdf->toon`: only tables are converted, so all other text is dropped.
  This is intended and noted in the UI.

## What came through intact

These pairs handled the main sample with no loss. A few of them (`csv->*`, `txt->pdf`,
`md->pdf`, `ipynb->pdf`) still fail the edge cases in findings 4 and 9. Each output was checked against the sample's content: sentinel words, accents, CJK where the
format supports it, image size and pixels, transparency, and page count.

- **Data:** `csv->md` (commas, quotes, embedded newlines, leading zeros, CJK), `csv->xlsx` (zip
  codes kept as text), `xlsx->csv` (one CSV per sheet in a zip, cached formula values kept),
  `json->toon` and `toon->json` (exact round trip), `toon->md`, `toon->pdf` (Latin text).
- **PDF:** `pdf->png` (one 600 DPI PNG per page, in a zip).
- **Office:** `pptx->pdf` (.pptx and .ppt: text, table, image).
- **Images:** `heic->jpg`, `heic->png`, `heic->pdf`, `jpg->png`, `jpg->webp`, `jpg->pdf`,
  `jpg->svg`, `png->jpg`, `png->webp`, `png->svg`, `webp->jpg`, `webp->png`, `webp->pdf`,
  `webp->svg`, `gif->pdf`, `gif->svg`, `svg->pdf` (correct px-to-pt size), `svg->png`.
  `.jpeg` behaves the same as `.jpg`. Lossless outputs matched the source pixel for pixel.
  Transparency kept in png/webp↔png/webp.
- **OCR:** `jpg->md`, `jpg->txt`, `heic->md`, and `img->txt` / `img->txt-tables` on png,
  bmp, tiff, webp: all read the sample text exactly.
- **Text/markup:** `md->pdf` (heading, table, list, code highlighting, math, Latin accents),
  `txt->pdf` (tabs, long-line wrapping, Latin accents), `html->pdf` and `.htm` (CSS colors and
  background kept), `html->svg` and `.htm`, `sql->pdf`, `ipynb->pdf` (cells and outputs),
  `rmd->pdf` (R chunk run, output shown).

## Not tested

- **LLM routes** (`pdf->md-local/-ai/-claude`, `handwriting->md*` for .jpg/.jpeg/.pdf): no
  Ollama or API keys in this environment. The server refused them up front with its
  missing-dependency message, as it should.
- **`mp4->md`**: the Whisper model download from Hugging Face was blocked by this
  environment's network policy (`403 Forbidden`). This is not a bug in the converter.
- **`combine_files`** (`/api/combine`): this is a multi-file endpoint, not a format pair.

## Test environment

Tests ran on Linux (Ubuntu, Python 3.13, the repo's `uv sync` environment). The README says
the project is built for macOS, so a few things were set up **outside the repo** to imitate
macOS. These are environment shims, not code changes:

- Chrome: a script at `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` (the
  hardcoded path in `html_svg.py`) that runs Playwright's `chrome-headless-shell` with
  `--no-sandbox`. The full Chromium build hung forever on `--print-to-pdf` in this container.
  The shim was needed because the container runs as root.
- Menlo: `md_pdf.py` needs the Menlo font, so DejaVu Sans Mono was installed under the
  family name "Menlo". Without it, `md->pdf` fails with
  `fontspec Error: The font "Menlo" cannot be found` (expected off macOS, per the README).
- `ipynb->pdf` needs `jupyter` on `PATH`. Run outside `uv run`, it fails with
  `jupyter nbconvert not found` even though nbconvert is installed in the venv.
- Installed with apt: tesseract, pandoc, LibreOffice, wkhtmltopdf, TeX Live (XeLaTeX), and R
  with rmarkdown.

Sample files covered: CSV (quotes, embedded newlines, leading zeros, CJK), a two-sheet XLSX with
a formula, nested JSON and its TOON encoding, a 2-page PDF with a ruled table, JPG/JPEG/BMP/TIFF,
a transparent PNG/WebP, a 3-frame GIF, HEIC, SVG, DOCX (heading, bold, bullets, table, image,
header), PPTX (title, bullets, notes, table, picture) and its .ppt version, Markdown (table,
code, math, link, raw `<…>`), TXT, HTML/HTM with CSS, SQL, a notebook with outputs, R, Rmd, and
MP4. Each carries sentinel words (Zebra, Quokka, Narwhal, Axolotl…) so missing text could be
found automatically.
