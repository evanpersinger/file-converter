"""Tests for llm_md.py, the handwriting converter for JPGs and PDFs.

Ollama, the Anthropic SDK, and the OpenAI SDK are all mocked: no network calls, no real API
key, no Ollama server needed to run this file.
"""

from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest
import requests
from PIL import Image

import llm_md


# --- helpers -------------------------------------------------------------------------
def _make_pdf(path: Path, pages: int = 1) -> None:
    doc = fitz.open()
    for _ in range(pages):
        doc.new_page()
    doc.save(path)
    doc.close()


def _make_jpg(path: Path) -> None:
    Image.new("RGB", (10, 10), "white").save(path)


class FakeResponse:
    """Stands in for requests.Response, only the two methods the Ollama path calls."""

    def __init__(self, json_data: dict | None = None) -> None:
        self._json = json_data if json_data is not None else {}

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._json


class FakeAnthropic:
    """Stands in for anthropic.Anthropic, only the .messages.create(...) call."""

    def __init__(self, message: SimpleNamespace) -> None:
        self.calls: list[dict] = []

        def create(**kwargs) -> SimpleNamespace:
            self.calls.append(kwargs)
            return message

        self.messages = SimpleNamespace(create=create)


class FakeOpenAI:
    """Stands in for openai.OpenAI, only the .chat.completions.create(...) call."""

    def __init__(self, content: str | None) -> None:
        self.calls: list[dict] = []

        def create(**kwargs) -> SimpleNamespace:
            self.calls.append(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


def _text_message(text: str) -> SimpleNamespace:
    return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=text)])


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Point llm_md's Path globals at a throwaway pair of directories."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    monkeypatch.setattr(llm_md, "input_dir", input_dir)
    monkeypatch.setattr(llm_md, "output_dir", output_dir)
    return input_dir, output_dir


@pytest.fixture
def ollama_reachable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_md.requests, "get", lambda *a, **k: FakeResponse())


def _fake_ollama(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Replace the Ollama chat call, returning the list its request bodies are recorded in."""
    calls: list[dict] = []

    def fake_post(url, json, timeout):
        calls.append(json)
        return FakeResponse({"message": {"content": f"Page {len(calls)} content"}})

    monkeypatch.setattr(llm_md.requests, "post", fake_post)
    return calls


# --- no default model ------------------------------------------------------------------
@pytest.mark.parametrize(
    "convert",
    [
        llm_md.convert_handwriting_to_markdown_openai,
        llm_md.convert_handwriting_to_markdown_anthropic,
        llm_md.convert_handwriting_to_markdown_local,
    ],
)
def test_conversions_require_a_model_instead_of_defaulting_to_one(convert) -> None:
    """Nothing may run, or bill, on a model the user didn't choose."""
    with pytest.raises(TypeError):
        convert()


# --- folder loop ---------------------------------------------------------------------
def test_local_reports_when_input_is_empty(sandbox, ollama_reachable) -> None:
    assert llm_md.convert_handwriting_to_markdown_local("gemma4:12b") == "No JPG or PDF files found in input folder"


def test_local_reports_when_only_markdown_present(sandbox, ollama_reachable) -> None:
    input_dir, _ = sandbox
    (input_dir / "notes.md").write_text("hi")

    assert llm_md.convert_handwriting_to_markdown_local("gemma4:12b") == "That file is already in md format"


def test_local_only_takes_jpg_and_pdf_files(sandbox, ollama_reachable) -> None:
    input_dir, _ = sandbox
    (input_dir / "notes.txt").write_text("hi")
    (input_dir / "photo.png").write_bytes(b"not really a png")

    assert llm_md.convert_handwriting_to_markdown_local("gemma4:12b") == "No JPG or PDF files found in input folder"


def test_local_reports_when_ollama_is_unreachable(sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    input_dir, _ = sandbox
    _make_jpg(input_dir / "note.jpg")

    def raise_connection_error(*_args, **_kwargs):
        raise requests.exceptions.ConnectionError()

    monkeypatch.setattr(llm_md.requests, "get", raise_connection_error)
    calls = _fake_ollama(monkeypatch)

    result = llm_md.convert_handwriting_to_markdown_local("gemma4:12b")

    assert result.startswith("Error: Ollama not reachable")
    assert calls == []


# --- local (Ollama) ------------------------------------------------------------------
def test_local_sends_a_jpg_with_the_handwriting_prompt_and_the_chosen_model(
    sandbox, ollama_reachable, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, output_dir = sandbox
    _make_jpg(input_dir / "note.jpg")
    calls = _fake_ollama(monkeypatch)

    summary = llm_md.convert_handwriting_to_markdown_local("gemma4:12b")

    assert "note.md" in summary
    assert (output_dir / "note.md").read_text(encoding="utf-8") == "Page 1 content"
    assert calls[0]["model"] == "gemma4:12b"
    assert calls[0]["messages"][0]["content"] == llm_md._HANDWRITING_PROMPT
    assert len(calls[0]["messages"][0]["images"]) == 1


def test_local_accepts_the_jpeg_extension(sandbox, ollama_reachable, monkeypatch: pytest.MonkeyPatch) -> None:
    input_dir, output_dir = sandbox
    _make_jpg(input_dir / "note.jpeg")
    _fake_ollama(monkeypatch)

    llm_md.convert_handwriting_to_markdown_local("gemma4:12b")

    assert (output_dir / "note.md").exists()


def test_local_transcribes_a_multi_page_pdf_in_page_order(
    sandbox, ollama_reachable, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, output_dir = sandbox
    _make_pdf(input_dir / "notes.pdf", pages=2)
    calls = _fake_ollama(monkeypatch)

    llm_md.convert_handwriting_to_markdown_local("gemma4:12b")

    assert (output_dir / "notes.md").read_text(encoding="utf-8") == "Page 1 content\n\nPage 2 content"
    assert [c["messages"][0]["content"] for c in calls] == [llm_md._HANDWRITING_PROMPT] * 2


def test_local_stops_before_the_next_page_when_cancelled(
    sandbox, ollama_reachable, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, output_dir = sandbox
    _make_pdf(input_dir / "notes.pdf", pages=3)
    calls = _fake_ollama(monkeypatch)
    # Checked before each page starts, so once the first call is made page 1 finishes and
    # page 2 never starts.
    monkeypatch.setattr(llm_md, "should_cancel", lambda: len(calls) >= 1)

    summary = llm_md.convert_handwriting_to_markdown_local("gemma4:12b")

    assert len(calls) == 1
    assert (output_dir / "notes.md").read_text(encoding="utf-8") == "Page 1 content"
    assert "Converted 1 file(s)" in summary


def test_a_password_protected_pdf_is_reported_as_a_failed_file(
    sandbox, ollama_reachable, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, _ = sandbox
    doc = fitz.open()
    doc.new_page()
    doc.save(input_dir / "locked.pdf", encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="secret")
    doc.close()
    calls = _fake_ollama(monkeypatch)

    summary = llm_md.convert_handwriting_to_markdown_local("gemma4:12b")

    assert "password protected" in summary
    assert calls == []


def test_an_empty_transcription_is_reported_instead_of_written(
    sandbox, ollama_reachable, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, output_dir = sandbox
    _make_jpg(input_dir / "note.jpg")
    monkeypatch.setattr(
        llm_md.requests, "post", lambda url, json, timeout: FakeResponse({"message": {"content": "  "}})
    )

    summary = llm_md.convert_handwriting_to_markdown_local("gemma4:12b")

    assert "conversion returned no content" in summary
    assert not (output_dir / "note.md").exists()


# --- Anthropic -----------------------------------------------------------------------
def test_anthropic_reports_a_missing_key(sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    result = llm_md.convert_handwriting_to_markdown_anthropic("claude-sonnet-5")

    assert result.startswith("Error: ANTHROPIC_API_KEY not found")


def test_anthropic_sends_the_image_and_prompt_and_uses_the_chosen_model(
    sandbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, output_dir = sandbox
    _make_jpg(input_dir / "note.jpg")
    client = FakeAnthropic(_text_message("hello"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(llm_md.anthropic, "Anthropic", lambda: client)

    summary = llm_md.convert_handwriting_to_markdown_anthropic("claude-haiku-4-5-20251001")

    assert "note.md" in summary
    assert (output_dir / "note.md").read_text(encoding="utf-8") == "hello"
    request = client.calls[0]
    assert request["model"] == "claude-haiku-4-5-20251001"
    image_block, text_block = request["messages"][0]["content"]
    assert image_block["source"]["media_type"] == "image/jpeg"
    assert text_block["text"] == llm_md._HANDWRITING_PROMPT


def test_anthropic_sends_each_pdf_page_as_a_png(sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    input_dir, output_dir = sandbox
    _make_pdf(input_dir / "notes.pdf", pages=2)
    client = FakeAnthropic(_text_message("page"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(llm_md.anthropic, "Anthropic", lambda: client)

    llm_md.convert_handwriting_to_markdown_anthropic("claude-sonnet-5")

    assert len(client.calls) == 2
    assert client.calls[0]["messages"][0]["content"][0]["source"]["media_type"] == "image/png"
    assert (output_dir / "notes.md").read_text(encoding="utf-8") == "page\n\npage"


def test_anthropic_raises_when_claude_refuses() -> None:
    client = FakeAnthropic(SimpleNamespace(stop_reason="refusal", content=[]))

    with pytest.raises(RuntimeError, match="declined"):
        llm_md._image_anthropic(client, "claude-sonnet-5", "aGk=", "image/jpeg")


def test_anthropic_raises_when_output_is_cut_off() -> None:
    client = FakeAnthropic(SimpleNamespace(stop_reason="max_tokens", content=[]))

    with pytest.raises(RuntimeError, match="cut off"):
        llm_md._image_anthropic(client, "claude-sonnet-5", "aGk=", "image/jpeg")


def test_anthropic_ignores_blocks_that_are_not_text() -> None:
    message = SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="thinking", text=None), SimpleNamespace(type="text", text="hello")],
    )

    assert llm_md._image_anthropic(FakeAnthropic(message), "claude-sonnet-5", "aGk=", "image/jpeg") == "hello"


# --- OpenAI --------------------------------------------------------------------------
def test_openai_reports_a_missing_key(sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = llm_md.convert_handwriting_to_markdown_openai("gpt-4o")

    assert result.startswith("Error: OPENAI_API_KEY not found")


def test_openai_sends_the_image_and_prompt_and_uses_the_chosen_model(
    sandbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, output_dir = sandbox
    _make_jpg(input_dir / "note.jpg")
    client = FakeOpenAI("hello")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(llm_md, "OpenAI", lambda api_key: client)

    summary = llm_md.convert_handwriting_to_markdown_openai("gpt-4o")

    assert "note.md" in summary
    assert (output_dir / "note.md").read_text(encoding="utf-8") == "hello"
    request = client.calls[0]
    assert request["model"] == "gpt-4o"
    text_part, image_part = request["messages"][0]["content"]
    assert text_part["text"] == llm_md._HANDWRITING_PROMPT
    assert image_part["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_openai_returns_an_empty_string_when_the_reply_has_no_content() -> None:
    assert llm_md._image_openai(FakeOpenAI(None), "gpt-4o", "aGk=", "image/jpeg") == ""
