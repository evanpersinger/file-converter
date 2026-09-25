"""Convert handwritten JPGs and PDFs in input/ to Markdown in output/ using an LLM.

Exists because Tesseract (jpg_md.py, pdf_md.py) can't read handwriting. OpenAI and Claude need
OPENAI_API_KEY / ANTHROPIC_API_KEY (env or .env) and cost money, local needs Ollama, free.
"""

import base64
import os
import sys
from collections.abc import Callable
from pathlib import Path

import anthropic
import fitz  # PyMuPDF
import requests
from openai import OpenAI

from llm_pdf_md import (
    LOCAL_RENDER_DPI,
    OLLAMA_HOST,
    _convert_page_ollama,
    _convert_pdf_local,
    _prompt_for_local_model,
    _prompt_for_provider,
)

# Define input and output directories relative to this script
script_dir = Path(__file__).resolve().parent
input_dir = script_dir / "input"   # Folder containing files to convert
output_dir = script_dir / "output"  # Folder where converted files will be saved

_HANDWRITING_PROMPT = (
    "Transcribe the handwriting in this image. Mark any word you cannot read as [illegible]."
)


# OpenAI (one image per call)
def _image_openai(client: OpenAI, model: str, image_b64: str, media_type: str) -> str:
    """Send one image to OpenAI and return its transcription."""
    response = client.chat.completions.create(
        model=model,
        temperature=0,  # faithful transcription, same as the other paths
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": _HANDWRITING_PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_b64}"}},
            ],
        }],
    )
    return response.choices[0].message.content or ""


# Anthropic (one image per call)
def _image_anthropic(client: anthropic.Anthropic, model: str, image_b64: str, media_type: str) -> str:
    """Send one image to Claude and return its transcription.

    The SDK already retries rate limits, server errors, and dropped connections, so there is
    no retry loop here.
    """
    message = client.messages.create(
        model=model,
        max_tokens=16000,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                {"type": "text", "text": _HANDWRITING_PROMPT},
            ],
        }],
    )

    if message.stop_reason == "refusal":
        raise RuntimeError("Claude declined to process this image")
    if message.stop_reason == "max_tokens":
        raise RuntimeError("output was cut off")

    return "".join(block.text for block in message.content if block.type == "text")


def _convert_pdf_pages(pdf_path: Path, convert_image: Callable[[str, str], str]) -> str:
    """Render each page of the PDF to an image and transcribe them one at a time.

    convert_image takes a base64 image and its media type, and returns the transcription.
    """
    doc = fitz.open(pdf_path)
    if doc.is_encrypted and not doc.authenticate(""):
        doc.close()
        raise ValueError("PDF is password protected")

    page_count = doc.page_count
    pages = []
    for i, page in enumerate(doc, start=1):
        print(f"\rConverting page {i}/{page_count}", end="", flush=True)
        png_bytes = page.get_pixmap(dpi=LOCAL_RENDER_DPI).tobytes("png")
        image_b64 = base64.standard_b64encode(png_bytes).decode("ascii")
        pages.append(convert_image(image_b64, "image/png"))
    doc.close()
    print()

    return "\n\n".join(pages)


def _convert_file(path: Path, convert_image: Callable[[str, str], str]) -> str:
    """Transcribe one JPG, or every page of one PDF, with the given image converter."""
    if path.suffix.lower() == ".pdf":
        return _convert_pdf_pages(path, convert_image)
    image_b64 = base64.standard_b64encode(path.read_bytes()).decode("ascii")
    return convert_image(image_b64, "image/jpeg")


def _convert_local(path: Path, model: str) -> str:
    """Transcribe one JPG or PDF with the local Ollama model."""
    if path.suffix.lower() == ".pdf":
        return _convert_pdf_local(path, model, _HANDWRITING_PROMPT)
    image_b64 = base64.standard_b64encode(path.read_bytes()).decode("ascii")
    return _convert_page_ollama(image_b64, model, _HANDWRITING_PROMPT)


# Shared folder loop
def _convert_all(convert_one: Callable[[Path], str]) -> str:
    """Run convert_one over every JPG and PDF in input_dir and write each result to output_dir.

    convert_one takes a file path and returns the full Markdown text for that file.
    Returns a summary of what was converted, suitable for showing to a caller.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    entries = list(os.listdir(input_dir)) if input_dir.is_dir() else []
    names = [n for n in entries if n.lower().endswith((".jpg", ".jpeg", ".pdf"))]

    # If there are no JPGs or PDFs but there are Markdown files, say so and stop
    if not names:
        if any(n.lower().endswith(".md") for n in entries):
            return "That file is already in md format"
        return "No JPG or PDF files found in input folder"

    converted = []
    errors = []

    for name in names:
        path = input_dir / name

        try:
            print(f"Converting {name} to md")
            text = convert_one(path)

            if not text or not text.strip():
                print(f"Failed to convert {name}")
                errors.append(f"{name}: conversion returned no content")
                continue

            out_md = f"{path.stem}.md"
            existed_before = (output_dir / out_md).exists()
            (output_dir / out_md).write_text(text, encoding="utf-8")

            print(f"Converted {name} to {out_md}")
            if existed_before:
                print(f"Overwrote existing file: {out_md}")
            converted.append(out_md)

        except Exception as e:
            print(f"Error converting {name}: {e}")
            errors.append(f"{name}: {e}")

    if not converted:
        return f"No files converted. {len(errors)} failed: {'; '.join(errors)}"

    summary = f"Converted {len(converted)} file(s) to output/: {', '.join(converted)}"
    if errors:
        summary += f". {len(errors)} failed: {'; '.join(errors)}"
    return summary


# Public entry points
def convert_handwriting_to_markdown_openai(model: str) -> str:
    """Convert all JPG and PDF files in the input folder to Markdown using OpenAI's Vision API.

    Costs money and sends the files to OpenAI. Requires OPENAI_API_KEY to be set in the
    environment or a .env file.

    Args:
        model: OpenAI model to use.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return "Error: OPENAI_API_KEY not found. Please add OPENAI_API_KEY to your .env file"

    client = OpenAI(api_key=api_key)
    return _convert_all(
        lambda path: _convert_file(path, lambda b64, media_type: _image_openai(client, model, b64, media_type))
    )


def convert_handwriting_to_markdown_anthropic(model: str) -> str:
    """Convert all JPG and PDF files in the input folder to Markdown using Anthropic's Claude.

    Costs money and sends the files to Anthropic. Requires ANTHROPIC_API_KEY to be set in the
    environment or a .env file. PDFs are sent one page image at a time, so there is no page or
    file size cap on the PDF itself.

    Args:
        model: Anthropic model to use.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return "Error: ANTHROPIC_API_KEY not found. Please add ANTHROPIC_API_KEY to your .env file"

    client = anthropic.Anthropic()
    return _convert_all(
        lambda path: _convert_file(path, lambda b64, media_type: _image_anthropic(client, model, b64, media_type))
    )


def convert_handwriting_to_markdown_local(model: str) -> str:
    """Convert all JPG and PDF files in the input folder to Markdown using a local Ollama model.

    Free, no API key or internet needed. Requires Ollama running locally with a vision-capable
    model pulled. Slower than the cloud paths and quality depends on the model.

    Args:
        model: name of a locally pulled Ollama model, as shown by `ollama list`.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    try:
        requests.get(f"{OLLAMA_HOST}/api/version", timeout=2).raise_for_status()
    except requests.exceptions.RequestException:
        return f"Error: Ollama not reachable at {OLLAMA_HOST}. Run `ollama serve` (or open the Ollama app)."

    return _convert_all(lambda path: _convert_local(path, model))


if __name__ == "__main__":
    # Usage: python backend/llm_md.py [openai|anthropic|local] [model]
    # With no arguments, shows a menu of ChatGPT/Anthropic/Open Source models to pick from.
    # For "local" with no model given, prompts interactively from installed Ollama models.
    # There is no default model: openai and anthropic exit with a usage message without one.
    if len(sys.argv) > 1:
        provider = sys.argv[1]
        chosen_model = sys.argv[2] if len(sys.argv) > 2 else None
    else:
        provider, chosen_model = _prompt_for_provider()

    if provider == "local":
        result = convert_handwriting_to_markdown_local(chosen_model or _prompt_for_local_model())
    elif provider == "anthropic" and chosen_model:
        result = convert_handwriting_to_markdown_anthropic(chosen_model)
    elif provider == "openai" and chosen_model:
        result = convert_handwriting_to_markdown_openai(chosen_model)
    else:
        sys.exit("Usage: python backend/llm_md.py [openai|anthropic|local] [model] (openai and anthropic need a model)")

    if not result.startswith("Converted"):
        print(result)
