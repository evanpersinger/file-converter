"""Convert PDFs in input/ to Markdown in output/ using an LLM. Slower than pdf_md.py.

OpenAI path needs OPENAI_API_KEY, Claude path needs ANTHROPIC_API_KEY (env or .env), both
cost money. Local path needs Ollama running with a vision model pulled, free.
"""

import base64
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path

import anthropic
import fitz  # PyMuPDF
import requests
from dotenv import load_dotenv

load_dotenv()

# Define input and output directories relative to this script
script_dir = Path(__file__).resolve().parent
input_dir = script_dir / "input"   # Folder containing files to convert
output_dir = script_dir / "output"  # Folder where converted files will be saved

OPENAI_MODELS = ["gpt-4o-mini", "gpt-4o"]  # vision_parse only supports these two for OpenAI
ANTHROPIC_MODELS = ["claude-sonnet-5", "claude-haiku-4-5-20251001"]
OPENAI_MODEL = OPENAI_MODELS[0]
ANTHROPIC_MODEL = ANTHROPIC_MODELS[0]
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = "qwen3.5:9b"
OLLAMA_KEEP_ALIVE = "30s"  # stop running the model 30 seconds after script completes conversion, overrides Ollama's 5 min default
LOCAL_RENDER_DPI = 200  # readable for a vision model without ballooning image size/latency

_DOCUMENT_PROMPT = (
    "Convert this PDF to Markdown. Reproduce the text faithfully and completely, do not "
    "summarize or paraphrase. Keep headings, lists, and emphasis. Render tables as "
    "Markdown tables and equations as LaTeX. Separate pages with a blank line. Output "
    "only the Markdown, with no preamble or commentary."
)

_PAGE_PROMPT = (
    "Convert this page image to Markdown. Reproduce the text faithfully and completely, do "
    "not summarize or paraphrase. Keep headings, lists, and emphasis. Render tables as "
    "Markdown tables and equations as LaTeX. Output only the Markdown for this page, with no "
    "preamble or commentary."
)


# OpenAI (via vision-parse)
def convert_with_retry(parser, pdf_path, max_retries=3, retry_delay=5):
    """Convert PDF with retry logic for connection errors"""
    for attempt in range(max_retries):
        try:
            # Convert PDF to markdown (returns list of pages)
            pages = parser.convert_pdf(str(pdf_path))
            return pages
        except Exception as e:
            error_msg = str(e).lower()
            # Check if it's a connection error
            if "connection" in error_msg or "timeout" in error_msg or "network" in error_msg:
                if attempt < max_retries - 1:
                    print(f"Connection error (attempt {attempt + 1}/{max_retries}). Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                else:
                    raise Exception(f"Connection failed after {max_retries} attempts: {e}")
            else:
                # Not a connection error, don't retry
                raise e
    return None


def _build_parser(api_key: str, model: str):
    """Build the VisionParser, falling back to URL mode if base64 is unavailable.

    vision_parse is imported here, not at module scope, because it calls
    nest_asyncio.apply() on import and that raises under uvloop. Keeping it inside this
    function means only the OpenAI path needs `--loop asyncio`, not the whole module.
    """
    from vision_parse import VisionParser

    # Try "base64" mode first as it's more reliable than "url" for local files
    try:
        return VisionParser(
            model_name=model,                   # OpenAI model for processing
            api_key=api_key,                    # API key from environment
            temperature=0,                      # Deterministic, faithful extraction (no paraphrasing)
            image_mode="base64",                # Process images as base64 (more reliable than URL)
            detailed_extraction=True,           # Capture tables, equations, and complex layouts
            enable_concurrency=False,           # Disable concurrency to avoid connection issues
            custom_prompt=_PAGE_PROMPT, # vision_parse calls per page, same shape as the local path
        )
    except Exception as e:
        # Fallback to URL mode if base64 doesn't work
        print(f"Warning: Could not initialize with base64 mode, trying URL mode: {e}")
        return VisionParser(
            model_name=model,
            api_key=api_key,
            temperature=0,
            image_mode="url",
            detailed_extraction=True,
            enable_concurrency=False,
            custom_prompt=_PAGE_PROMPT,
        )


# Anthropic (Claude reads the PDF directly)
def _convert_pdf_anthropic(client: anthropic.Anthropic, pdf_path: Path, model: str) -> str:
    """Send one PDF to Claude as a document block and return the Markdown it writes back.

    Streams the response so long documents do not hit the HTTP timeout. The SDK already
    retries rate limits, server errors, and dropped connections, so there is no retry
    loop here.
    """
    pdf_b64 = base64.standard_b64encode(pdf_path.read_bytes()).decode("ascii")

    with client.messages.stream(
        model=model,
        max_tokens=64000,
        # Transcribing a PDF needs little reasoning. Low effort keeps thinking short, which
        # is billed as output and counts against max_tokens.
        output_config={"effort": "low"},
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": pdf_b64,
                    },
                },
                {"type": "text", "text": _DOCUMENT_PROMPT},
            ],
        }],
    ) as stream:
        message = stream.get_final_message()

    if message.stop_reason == "refusal":
        raise RuntimeError("Claude declined to process this PDF")
    if message.stop_reason == "max_tokens":
        raise RuntimeError("output was cut off, the PDF is too long (roughly 100 pages max, fewer if dense)")

    return "".join(block.text for block in message.content if block.type == "text")


# Local (Ollama reads each page as an image, no API key or internet needed)
def _convert_page_ollama(image_b64: str, model: str) -> str:
    """Send one rendered page to the local Ollama vision model and return its Markdown."""
    response = requests.post(
        f"{OLLAMA_HOST}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": _PAGE_PROMPT, "images": [image_b64]}],
            "stream": False,
            # Faithful transcription, not conversation. The model's default (1) leaves room
            # to paraphrase; 0 keeps it deterministic, same reasoning as the OpenAI/Claude paths.
            "options": {"temperature": 0},
            # Transcription needs no reasoning. On models that support it (qwen3.5, etc.)
            # this skips the hidden chain-of-thought that otherwise runs before every page.
            "think": False,
            "keep_alive": OLLAMA_KEEP_ALIVE,
        },
        # Local vision models are slow, especially on CPU. A single page can take a while.
        timeout=300,
    )
    response.raise_for_status()
    return response.json()["message"]["content"]


def _convert_pdf_local(pdf_path: Path, model: str) -> str:
    """Render each page of the PDF to an image and transcribe it with the local Ollama model.

    Page by page, like the OpenAI path, since local vision models handle one image far more
    reliably than a whole multi-page document at once.
    """
    doc = fitz.open(pdf_path)
    if doc.is_encrypted and not doc.authenticate(""):
        doc.close()
        raise ValueError("PDF is password protected")

    pages = []
    for page in doc:
        png_bytes = page.get_pixmap(dpi=LOCAL_RENDER_DPI).tobytes("png")
        image_b64 = base64.standard_b64encode(png_bytes).decode("ascii")
        pages.append(_convert_page_ollama(image_b64, model))
    doc.close()

    return "\n\n".join(pages)


def list_ollama_models() -> list[str]:
    """Return the names of models currently pulled in the local Ollama installation."""
    response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
    response.raise_for_status()
    return [m["name"] for m in response.json().get("models", [])]


# Shared folder loop
def _convert_all(convert_one: Callable[[Path], str]) -> str:
    """Run convert_one over every PDF in input_dir and write each result to output_dir.

    convert_one takes a PDF path and returns the full Markdown text for that file.
    Returns a summary of what was converted, suitable for showing to a caller.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    entries = list(os.listdir(input_dir)) if input_dir.is_dir() else []
    pdf_names = [n for n in entries if n.lower().endswith(".pdf")]

    # If there are no PDFs but there are Markdown files, say so and stop
    if not pdf_names:
        if any(n.lower().endswith(".md") for n in entries):
            return "That file is already in md format"
        return "No PDF files found in input folder"

    converted = []
    errors = []

    for pdf_name in pdf_names:
        pdf_path = input_dir / pdf_name

        try:
            print(f"Processing {pdf_name}...")
            full_md = convert_one(pdf_path)

            if not full_md:
                print(f"Failed to convert {pdf_name}")
                errors.append(f"{pdf_name}: conversion returned no content")
                continue

            out_md = f"{pdf_path.stem}.md"
            (output_dir / out_md).write_text(full_md, encoding="utf-8")

            print(f"Converted {pdf_name} -> {out_md}")
            converted.append(out_md)

        except Exception as e:
            print(f"Error converting {pdf_name}: {e}")
            print("Tip: If this is an image-based PDF, try converting the original JPG/PNG instead")
            errors.append(f"{pdf_name}: {e}")
            continue

    if not converted:
        return f"No files converted. {len(errors)} failed: {'; '.join(errors)}"

    summary = f"Converted {len(converted)} file(s) to output/: {', '.join(converted)}"
    if errors:
        summary += f". {len(errors)} failed: {'; '.join(errors)}"
    return summary


# Public entry points
def convert_pdf_to_markdown_openai(model: str = OPENAI_MODEL) -> str:
    """Convert all PDF files in the input folder to Markdown using OpenAI's Vision API.

    Higher quality than the local pdf_md.py converter, but slower and it costs money.
    Requires OPENAI_API_KEY to be set in the environment or a .env file.

    Args:
        model: OpenAI model to use. Defaults to OPENAI_MODEL.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    # Check the API key here rather than at import time, so importing this module
    # never kills the calling process.
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return "Error: OPENAI_API_KEY not found. Please add OPENAI_API_KEY to your .env file"

    parser = _build_parser(api_key, model)
    return _convert_all(lambda pdf_path: "\n\n".join(convert_with_retry(parser, pdf_path) or []))


def convert_pdf_to_markdown_anthropic(model: str = ANTHROPIC_MODEL) -> str:
    """Convert all PDF files in the input folder to Markdown using Anthropic's Claude.

    Higher quality than the local pdf_md.py converter, but slower and it costs money.
    Requires ANTHROPIC_API_KEY to be set in the environment or a .env file.
    Handles roughly 100 pages per PDF, fewer for dense text or tables. Longer PDFs
    hit the 64K output cap and fail.

    Args:
        model: Anthropic model to use. Defaults to ANTHROPIC_MODEL.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return "Error: ANTHROPIC_API_KEY not found. Please add ANTHROPIC_API_KEY to your .env file"

    client = anthropic.Anthropic()
    return _convert_all(lambda pdf_path: _convert_pdf_anthropic(client, pdf_path, model))


def convert_pdf_to_markdown_local(model: str = OLLAMA_MODEL) -> str:
    """Convert all PDF files in the input folder to Markdown using a local Ollama vision model.

    Free, no API key or internet needed. Requires Ollama running locally with a vision-capable
    model pulled. Slower than the cloud paths and quality depends on the model.

    Args:
        model: name of a locally pulled Ollama model, as shown by `ollama list`. Defaults to
            OLLAMA_MODEL.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    # Checked here rather than at import time, so importing this module never kills the
    # calling process, and checked once up front instead of once per PDF.
    try:
        requests.get(f"{OLLAMA_HOST}/api/version", timeout=2).raise_for_status()
    except requests.exceptions.RequestException:
        return f"Error: Ollama not reachable at {OLLAMA_HOST}. Run `ollama serve` (or open the Ollama app)."

    return _convert_all(lambda pdf_path: _convert_pdf_local(pdf_path, model))


def _prompt_for_local_model() -> str:
    """Ask the user to pick one of the locally installed Ollama models. CLI entry point only,
    callers going through the web UI or the agent must pass a model instead of hitting this."""
    try:
        models = list_ollama_models()
    except requests.exceptions.RequestException:
        print(f"Could not reach Ollama at {OLLAMA_HOST}, using default: {OLLAMA_MODEL}")
        return OLLAMA_MODEL

    if not models:
        print(f"No Ollama models installed, using default: {OLLAMA_MODEL}")
        return OLLAMA_MODEL

    print("Installed Ollama models:")
    for i, name in enumerate(models, start=1):
        print(f"  {i}) {name}")

    choice = input("Select a model: ").strip()
    if not choice:
        return models[0]
    if choice.isdigit() and 1 <= int(choice) <= len(models):
        return models[int(choice) - 1]

    print(f"Invalid choice, using {models[0]}")
    return models[0]


def _prompt_for_provider() -> tuple[str, str]:
    """Ask the user to pick a model across all three provider sections. CLI entry point
    only, callers going through the web UI or the agent must pass a provider and model
    instead of hitting this.

    Returns (provider, model).
    """
    try:
        local_models = list_ollama_models()
    except requests.exceptions.RequestException:
        local_models = []

    entries: list[tuple[str, str]] = (
        [("openai", name) for name in OPENAI_MODELS]
        + [("anthropic", name) for name in ANTHROPIC_MODELS]
        + [("local", name) for name in local_models]
    )

    i = 1
    print("ChatGPT models:")
    for name in OPENAI_MODELS:
        print(f"  {i}) {name}")
        i += 1
    print("Anthropic models:")
    for name in ANTHROPIC_MODELS:
        print(f"  {i}) {name}")
        i += 1
    print("OS models:")
    if local_models:
        for name in local_models:
            print(f"  {i}) {name}")
            i += 1
    else:
        print("  (none installed)")

    while True:
        choice = input("Select a model: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(entries):
            return entries[int(choice) - 1]
        print("Enter a number from the list above.")


if __name__ == "__main__":
    # Usage: python backend/llm_pdf_md.py [openai|anthropic|local] [model]
    # With no arguments, shows a menu of ChatGPT/Anthropic/OS models to pick from.
    # For "local" with no model given, prompts interactively from installed Ollama models.
    if len(sys.argv) > 1:
        provider = sys.argv[1]
        chosen_model = sys.argv[2] if len(sys.argv) > 2 else None
    else:
        provider, chosen_model = _prompt_for_provider()

    if provider == "anthropic":
        print(convert_pdf_to_markdown_anthropic(chosen_model or ANTHROPIC_MODEL))
    elif provider == "local":
        print(convert_pdf_to_markdown_local(chosen_model or _prompt_for_local_model()))
    else:
        print(convert_pdf_to_markdown_openai(chosen_model or OPENAI_MODEL))
