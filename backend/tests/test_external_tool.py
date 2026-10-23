"""Tests for external_tool.py: the time limit on external tools, and that a timeout leaves
nothing of the tool running. The tools here are shell one-liners, so no real pandoc or
tesseract is needed.
"""

import os
import time
from pathlib import Path

import pytest
import pytesseract
from PIL import Image

import external_tool
from external_tool import ToolTimeout, ocr_text, run_tool


def test_run_tool_captures_output_and_exit_code() -> None:
    result = run_tool(["sh", "-c", "echo out; echo err >&2; exit 3"])

    assert (result.stdout, result.stderr, result.returncode) == ("out\n", "err\n", 3)


def test_run_tool_passes_keyword_arguments_through(tmp_path: Path) -> None:
    result = run_tool(["pwd"], cwd=tmp_path)

    assert Path(result.stdout.strip()).resolve() == tmp_path.resolve()


def test_run_tool_gives_the_tool_no_input() -> None:
    """A tool that stops to ask a question has to fail at once, not wait out the limit."""
    assert run_tool(["sh", "-c", "read answer; echo got:$answer"]).stdout == "got:\n"


def test_a_tool_over_the_limit_is_stopped_with_a_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(external_tool, "TOOL_TIMEOUT_SECONDS", 1)

    with pytest.raises(ToolTimeout, match="sleep took longer than 1 seconds"):
        run_tool(["sleep", "30"])


def test_a_timeout_also_stops_what_the_tool_started(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """subprocess.run(timeout=) alone would leave this grandchild running, which is what
    xelatex does when pandoc is killed."""
    monkeypatch.setattr(external_tool, "TOOL_TIMEOUT_SECONDS", 1)
    pid_file = tmp_path / "pid"

    with pytest.raises(ToolTimeout):
        run_tool(["sh", "-c", f"sleep 30 & echo $! > '{pid_file}'; wait"])

    grandchild = int(pid_file.read_text())
    deadline = time.time() + 2
    while time.time() < deadline:
        try:
            os.kill(grandchild, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    pytest.fail("the process the tool started is still running")


def _fake_tesseract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str) -> None:
    script = tmp_path / "tesseract"
    script.write_text(f"#!/bin/sh\n{body}\n")
    script.chmod(0o755)
    monkeypatch.setattr(pytesseract.pytesseract, "tesseract_cmd", str(script))


def test_ocr_text_stops_a_hung_tesseract_with_a_clear_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Also pins pytesseract's timeout message, which is how a timeout is told apart."""
    _fake_tesseract(tmp_path, monkeypatch, "exec sleep 30")
    monkeypatch.setattr(external_tool, "TOOL_TIMEOUT_SECONDS", 1)

    with pytest.raises(ToolTimeout, match="tesseract took longer than 1 seconds"):
        ocr_text(Image.new("RGB", (10, 10)))


def test_ocr_text_leaves_other_tesseract_errors_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_tesseract(tmp_path, monkeypatch, "echo boom >&2; exit 1")

    with pytest.raises(RuntimeError) as raised:
        ocr_text(Image.new("RGB", (10, 10)))

    assert not isinstance(raised.value, ToolTimeout)
