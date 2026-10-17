# File Converter

Convert files between formats from a local web UI or from standalone Python scripts.

## Run it

```bash
# Terminal 1: frontend
cd frontend && pnpm install && pnpm dev

# Terminal 2: backend (the flags are required)
uv sync
uv run uvicorn server:app --app-dir backend --reload --port 8019 --loop asyncio
```

Open http://localhost:3004. Both have to be running.

Pick files, pick a target format, convert, download. **View** previews a file before or
after converting. The **Convert Files (LLM)** tab turns PDFs and handwriting photos into
Markdown with an LLM: local Ollama (free, pull the model first with `ollama pull <model>`),
OpenAI, or Anthropic (the last two cost money and need `OPENAI_API_KEY` or
`ANTHROPIC_API_KEY` in `.env`).

## What it converts

- **PDF** to Markdown (OCR or LLM), PNG
- **Word** to Markdown, PDF
- **PowerPoint** to PDF, Markdown
- **Markdown, HTML, TXT, SQL, Jupyter, R Markdown** to PDF
- **Excel, CSV** to each other, CSV to Markdown
- **JPG, PNG, GIF, WebP, HEIC** to PDF, PNG, JPG, SVG, Markdown or text (which ones depends on the source)
- Combine several files of one type into one

Every script is in `backend/<from>_<to>.py`. Each runs on its own: drop files in
`backend/input/`, run it, and find the results in `backend/output/`.

## System tools

Only the conversion you use needs its tool:

```bash
brew install libmagic                   # web UI server, always needed
brew install tesseract                  # OCR
brew install pandoc                     # Word and Markdown conversions
brew install --cask mactex              # Markdown and Jupyter to PDF
brew install --cask libreoffice         # PowerPoint
brew install wkhtmltopdf                # HTML to PDF
brew install ollama                     # local LLM
```

HTML to SVG needs Google Chrome. Mermaid diagrams in Markdown to PDF need
`pnpm add -g mermaid-filter`.

## Good to know

- Converting a file again overwrites the old output, and the script prints a message when it does.
- Combine only works on files that share one extension, and keeps the order you added them.
- Uploads are capped at 500 MB per request.
- The web UI runs one conversion at a time. A second one (another tab, say) waits for the
  first to finish, and the progress bar says "Waiting for another conversion...".
- Long PDFs on the LLM tab: the Claude path caps at about 100 pages (32 MB), and the
  OpenAI path can hit a rate limit and fail with no output. Use Claude for long ones.
- Local models are slow, often over a minute per page.
- OCR is English-only on purpose. Other languages come back as garbled English, not an error.
- Handwriting reads better from a scan than from a phone photo.
- `md_pdf.py` uses the Menlo font (ships with macOS). On Linux, change `\setmonofont` in the script.

Some chains give bad output, see [CONVERSIONS.md](CONVERSIONS.md).
