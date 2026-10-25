"""Run external tools (pandoc, soffice, Chrome, tesseract) with a time limit, so one that hangs
cannot hold a conversion, and its server slot, forever.
"""

import os
import signal
import subprocess
from pathlib import Path

import pytesseract

TOOL_TIMEOUT_SECONDS = 300

# What pytesseract raises when its own timeout fires. It is a plain RuntimeError, so the
# message is the only way to tell it from any other tesseract failure.
_PYTESSERACT_TIMEOUT_MESSAGE = "Tesseract process timeout"


class ToolTimeout(RuntimeError):
    """An external tool ran past TOOL_TIMEOUT_SECONDS and was stopped."""


def run_tool(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command and capture its text output, stopping it after TOOL_TIMEOUT_SECONDS.

    Works like subprocess.run(capture_output=True, text=True), plus a few differences. The tool
    runs in its own process group and the whole group is killed on a timeout, because
    subprocess.run(timeout=) kills only the tool itself and leaves what it started (xelatex
    under pandoc, soffice.bin under soffice) running. It reads no input, so a tool that stops
    to ask a question fails at once instead of waiting for the limit.

    Raises:
        ToolTimeout: If the tool runs longer than TOOL_TIMEOUT_SECONDS.
    """
    process = subprocess.Popen(
        command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, start_new_session=True, **kwargs,
    )
    try:
        stdout, stderr = process.communicate(timeout=TOOL_TIMEOUT_SECONDS)
    except BaseException as exc:
        # Also covers Ctrl-C, which no longer reaches the tool now it is in its own group.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate()
        if isinstance(exc, subprocess.TimeoutExpired):
            raise ToolTimeout(
                f"{Path(command[0]).name} took longer than {TOOL_TIMEOUT_SECONDS} seconds"
            ) from None
        raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def _ocr(read, image, **kwargs):
    """Call a pytesseract reader with a time limit, turning its timeout into a ToolTimeout."""
    try:
        return read(image, timeout=TOOL_TIMEOUT_SECONDS, **kwargs)
    except RuntimeError as exc:
        if str(exc) == _PYTESSERACT_TIMEOUT_MESSAGE:
            raise ToolTimeout(f"tesseract took longer than {TOOL_TIMEOUT_SECONDS} seconds") from None
        raise


def ocr_text(image, **kwargs) -> str:
    """pytesseract.image_to_string with a time limit.

    Raises:
        ToolTimeout: If tesseract runs longer than TOOL_TIMEOUT_SECONDS.
    """
    return _ocr(pytesseract.image_to_string, image, **kwargs)


def ocr_data(image, **kwargs) -> dict:
    """pytesseract.image_to_data with a time limit: every word tesseract found, with its
    confidence (0-100) and where it sits, as lists keyed by column name.

    Raises:
        ToolTimeout: If tesseract runs longer than TOOL_TIMEOUT_SECONDS.
    """
    return _ocr(pytesseract.image_to_data, image, output_type=pytesseract.Output.DICT, **kwargs)
