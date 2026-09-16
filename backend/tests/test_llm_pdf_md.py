"""Tests for llm_pdf_md.py's local (Ollama) and Anthropic paths.

Ollama and the Anthropic SDK are both mocked, no network calls, no real API key, no
Ollama server needed to run this file. The OpenAI path only wraps the third-party
vision_parse library, so it isn't covered here, mocking vision_parse's internals would
just be testing that library, not our code.
"""

from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest
import requests

import llm_pdf_md


# --- helpers -------------------------------------------------------------------------
def _make_pdf(path: Path, pages: int = 1) -> None:
    """Write a real, minimal PDF with `pages` blank pages, so fitz can open it for real."""
    doc = fitz.open()
    for _ in range(pages):
        doc.new_page()
    doc.save(path)
    doc.close()


def _make_encrypted_pdf(path: Path) -> None:
    doc = fitz.open()
    doc.new_page()
    doc.save(path, encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="secret")
    doc.close()


class FakeResponse:
    """Stands in for requests.Response, only the two methods llm_pdf_md calls."""

    def __init__(self, json_data: dict | None = None, status_code: int = 200) -> None:
        self._json = json_data if json_data is not None else {}
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"{self.status_code} error")

    def json(self) -> dict:
        return self._json


@pytest.fixture
def local_sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Point llm_pdf_md's Path globals at a throwaway pair of directories.

    llm_pdf_md reads `input_dir`/`output_dir` (Path objects) at call time, this is the
    same thing server.py's `via_dir_globals` patches for a real web UI request.
    """
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    monkeypatch.setattr(llm_pdf_md, "input_dir", input_dir)
    monkeypatch.setattr(llm_pdf_md, "output_dir", output_dir)
    return input_dir, output_dir


@pytest.fixture
def ollama_reachable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the /api/version reachability check in convert_pdf_to_markdown_local pass."""
    monkeypatch.setattr(llm_pdf_md.requests, "get", lambda *a, **k: FakeResponse())


# --- convert_pdf_to_markdown_local: folder-loop behavior -----------------------------
def test_local_reports_when_input_is_empty(local_sandbox, ollama_reachable) -> None:
    assert llm_pdf_md.convert_pdf_to_markdown_local() == "No PDF files found in input folder"


def test_local_reports_when_only_markdown_present(local_sandbox, ollama_reachable) -> None:
    input_dir, _ = local_sandbox
    (input_dir / "notes.md").write_text("hi")
    assert llm_pdf_md.convert_pdf_to_markdown_local() == "That file is already in md format"


def test_local_reports_when_ollama_is_unreachable(
    local_sandbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, _ = local_sandbox
    _make_pdf(input_dir / "doc.pdf")

    def raise_connection_error(*_args, **_kwargs):
        raise requests.exceptions.ConnectionError()

    monkeypatch.setattr(llm_pdf_md.requests, "get", raise_connection_error)
    posts: list[dict] = []
    monkeypatch.setattr(llm_pdf_md.requests, "post", lambda *a, **k: posts.append(k))

    result = llm_pdf_md.convert_pdf_to_markdown_local()

    assert result.startswith("Error: Ollama not reachable")
    assert posts == []  # never even tried to convert a page


def test_local_converts_multi_page_pdf_in_page_order(
    local_sandbox, ollama_reachable, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, output_dir = local_sandbox
    _make_pdf(input_dir / "doc.pdf", pages=2)
    calls: list[dict] = []

    def fake_post(url, json, timeout):
        calls.append(json)
        return FakeResponse({"message": {"content": f"Page {len(calls)} content"}})

    monkeypatch.setattr(llm_pdf_md.requests, "post", fake_post)

    summary = llm_pdf_md.convert_pdf_to_markdown_local("qwen3.5:9b")

    assert "doc.md" in summary
    markdown = (output_dir / "doc.md").read_text(encoding="utf-8")
    assert markdown == "Page 1 content\n\nPage 2 content"
    assert len(calls) == 2


def test_local_recognizes_uppercase_pdf_extension(
    local_sandbox, ollama_reachable, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, output_dir = local_sandbox
    _make_pdf(input_dir / "SCAN.PDF")
    monkeypatch.setattr(
        llm_pdf_md.requests, "post", lambda *a, **k: FakeResponse({"message": {"content": "x"}})
    )

    summary = llm_pdf_md.convert_pdf_to_markdown_local()

    assert "SCAN.md" in summary
    assert (output_dir / "SCAN.md").exists()


def test_local_sends_deterministic_options_and_the_chosen_model(
    local_sandbox, ollama_reachable, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression check: temperature=0 and the 30s keep_alive are actually on the
    request, and the model the caller asked for is the one that gets sent."""
    input_dir, _ = local_sandbox
    _make_pdf(input_dir / "doc.pdf")
    calls: list[dict] = []

    def fake_post(url, json, timeout):
        calls.append(json)
        return FakeResponse({"message": {"content": "text"}})

    monkeypatch.setattr(llm_pdf_md.requests, "post", fake_post)

    llm_pdf_md.convert_pdf_to_markdown_local("gemma4:12b")

    assert calls[0]["model"] == "gemma4:12b"
    assert calls[0]["options"]["temperature"] == 0
    assert calls[0]["keep_alive"] == llm_pdf_md.OLLAMA_KEEP_ALIVE


def test_local_defaults_to_the_configured_model_when_none_given(
    local_sandbox, ollama_reachable, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, _ = local_sandbox
    _make_pdf(input_dir / "doc.pdf")
    calls: list[dict] = []

    def fake_post(url, json, timeout):
        calls.append(json)
        return FakeResponse({"message": {"content": "text"}})

    monkeypatch.setattr(llm_pdf_md.requests, "post", fake_post)

    llm_pdf_md.convert_pdf_to_markdown_local()

    assert calls[0]["model"] == llm_pdf_md.OLLAMA_MODEL


def test_local_reports_password_protected_pdf_as_a_per_file_error(
    local_sandbox, ollama_reachable, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, _ = local_sandbox
    _make_encrypted_pdf(input_dir / "locked.pdf")
    monkeypatch.setattr(
        llm_pdf_md.requests, "post", lambda *a, **k: FakeResponse({"message": {"content": "x"}})
    )

    summary = llm_pdf_md.convert_pdf_to_markdown_local()

    assert "No files converted" in summary
    assert "password protected" in summary


def test_local_reports_malformed_ollama_response_as_a_per_file_error(
    local_sandbox, ollama_reachable, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An Ollama response missing the expected "message" key shouldn't crash the run,
    it should show up as that file's error, same as any other conversion failure."""
    input_dir, _ = local_sandbox
    _make_pdf(input_dir / "doc.pdf")
    monkeypatch.setattr(
        llm_pdf_md.requests, "post", lambda *a, **k: FakeResponse({"unexpected": "shape"})
    )

    summary = llm_pdf_md.convert_pdf_to_markdown_local()

    assert "No files converted" in summary
    assert "doc.pdf" in summary


def test_local_reports_empty_page_content_as_no_content(
    local_sandbox, ollama_reachable, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, _ = local_sandbox
    _make_pdf(input_dir / "blank.pdf")
    monkeypatch.setattr(
        llm_pdf_md.requests, "post", lambda *a, **k: FakeResponse({"message": {"content": ""}})
    )

    summary = llm_pdf_md.convert_pdf_to_markdown_local()

    assert "conversion returned no content" in summary


def test_local_reports_all_empty_pages_as_no_content(
    local_sandbox, ollama_reachable, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Joining several empty pages with "\\n\\n" produces a non-empty, whitespace-only
    string. That must still be reported as no content, not written out as a fake success."""
    input_dir, output_dir = local_sandbox
    _make_pdf(input_dir / "blank.pdf", pages=2)
    monkeypatch.setattr(
        llm_pdf_md.requests, "post", lambda *a, **k: FakeResponse({"message": {"content": ""}})
    )

    summary = llm_pdf_md.convert_pdf_to_markdown_local()

    assert "conversion returned no content" in summary
    assert not (output_dir / "blank.md").exists()


def test_local_continues_after_one_pdf_fails_mid_batch(
    local_sandbox, ollama_reachable, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One PDF's Ollama call blows up; the batch doesn't abort, the other PDF still
    converts, and the summary reports both outcomes."""
    input_dir, output_dir = local_sandbox
    _make_pdf(input_dir / "a.pdf")
    _make_pdf(input_dir / "b.pdf")
    call_count = 0

    def fake_post(url, json, timeout):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise requests.exceptions.ConnectionError("dropped")
        return FakeResponse({"message": {"content": "converted text"}})

    monkeypatch.setattr(llm_pdf_md.requests, "post", fake_post)

    summary = llm_pdf_md.convert_pdf_to_markdown_local()

    assert "Converted 1 file(s)" in summary
    assert "1 failed" in summary
    assert len(list(output_dir.glob("*.md"))) == 1


# --- list_ollama_models ----------------------------------------------------------------
def test_list_ollama_models_parses_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        llm_pdf_md.requests,
        "get",
        lambda *a, **k: FakeResponse(
            {"models": [{"name": "qwen3.5:9b"}, {"name": "gemma4:12b"}]}
        ),
    )
    assert llm_pdf_md.list_ollama_models() == ["qwen3.5:9b", "gemma4:12b"]


# --- _prompt_for_local_model -----------------------------------------------------------
def test_prompt_blank_input_picks_the_first_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_pdf_md, "list_ollama_models", lambda: ["qwen3.5:9b", "gemma4:12b"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": "")

    assert llm_pdf_md._prompt_for_local_model() == "qwen3.5:9b"


def test_prompt_valid_number_picks_that_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_pdf_md, "list_ollama_models", lambda: ["qwen3.5:9b", "gemma4:12b"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": "2")

    assert llm_pdf_md._prompt_for_local_model() == "gemma4:12b"


@pytest.mark.parametrize("bad_choice", ["abc", "0", "99", "-1", "1.5"])
def test_prompt_invalid_choice_falls_back_to_the_first_model(
    monkeypatch: pytest.MonkeyPatch, bad_choice: str
) -> None:
    monkeypatch.setattr(llm_pdf_md, "list_ollama_models", lambda: ["qwen3.5:9b", "gemma4:12b"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": bad_choice)

    assert llm_pdf_md._prompt_for_local_model() == "qwen3.5:9b"


def test_prompt_falls_back_to_default_when_no_models_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(llm_pdf_md, "list_ollama_models", lambda: [])

    assert llm_pdf_md._prompt_for_local_model() == llm_pdf_md.OLLAMA_MODEL


def test_prompt_falls_back_to_default_when_ollama_is_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_connection_error():
        raise requests.exceptions.ConnectionError()

    monkeypatch.setattr(llm_pdf_md, "list_ollama_models", raise_connection_error)

    assert llm_pdf_md._prompt_for_local_model() == llm_pdf_md.OLLAMA_MODEL


# --- _convert_pdf_anthropic --------------------------------------------------------------
class _FakeStream:
    def __init__(self, message: SimpleNamespace) -> None:
        self._message = message

    def __enter__(self) -> "_FakeStream":
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False

    def get_final_message(self) -> SimpleNamespace:
        return self._message


class _FakeAnthropicClient:
    """Stands in for anthropic.Anthropic, only the .messages.stream(...) call chain
    that _convert_pdf_anthropic actually uses."""

    def __init__(self, message: SimpleNamespace) -> None:
        self.messages = SimpleNamespace(stream=lambda **kwargs: _FakeStream(message))


def test_anthropic_raises_when_claude_refuses(tmp_path: Path) -> None:
    pdf_path = tmp_path / "doc.pdf"
    _make_pdf(pdf_path)
    client = _FakeAnthropicClient(SimpleNamespace(stop_reason="refusal", content=[]))

    with pytest.raises(RuntimeError, match="declined"):
        llm_pdf_md._convert_pdf_anthropic(client, pdf_path, llm_pdf_md.ANTHROPIC_MODEL)


def test_anthropic_raises_when_output_is_cut_off(tmp_path: Path) -> None:
    pdf_path = tmp_path / "doc.pdf"
    _make_pdf(pdf_path)
    client = _FakeAnthropicClient(SimpleNamespace(stop_reason="max_tokens", content=[]))

    with pytest.raises(RuntimeError, match="too long"):
        llm_pdf_md._convert_pdf_anthropic(client, pdf_path, llm_pdf_md.ANTHROPIC_MODEL)


def test_anthropic_returns_empty_string_when_there_are_no_text_blocks(tmp_path: Path) -> None:
    """A response with no text blocks (e.g. thinking-only) comes back empty rather than
    raising, so the shared _convert_all reports it as a real failed conversion instead
    of silently writing an empty file."""
    pdf_path = tmp_path / "doc.pdf"
    _make_pdf(pdf_path)
    message = SimpleNamespace(
        stop_reason="end_turn", content=[SimpleNamespace(type="thinking", text=None)]
    )
    client = _FakeAnthropicClient(message)

    assert llm_pdf_md._convert_pdf_anthropic(client, pdf_path, llm_pdf_md.ANTHROPIC_MODEL) == ""
