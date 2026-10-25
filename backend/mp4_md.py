"""Convert MP4 videos to Markdown: what was said (Whisper) and the text shown on screen
(Tesseract), on one timeline.
"""

import difflib
import re
import sys
from collections.abc import Callable
from pathlib import Path

import cv2
from faster_whisper import WhisperModel

from batch_convert import INPUT_DIR, OUTPUT_DIR, convert_files
from external_tool import ocr_data
from llm_pdf_md import not_cancelled

# The Whisper sizes on offer. Anything else is refused instead of handed to faster-whisper,
# which would read an unknown name as a Hugging Face repo to download.
WHISPER_MODELS = ("tiny", "base", "small", "medium", "large-v3")

# Seconds between the frames read for on-screen text.
FRAME_INTERVAL_SECONDS = 2
# Mean pixel difference (0-255) under which a frame is the same picture as the last one
# read, so it is not read again.
SAME_PICTURE_DIFF = 2.0
# How alike two readings of a screen must be (0-1) to count as the same text. OCR reads one
# slide a little differently from frame to frame.
SAME_TEXT_RATIO = 0.9
# Tesseract rates each word it reads from 0 to 100. Below MIN_WORD_CONFIDENCE a word is not
# trusted and is left out. A frame where fewer than MIN_CONFIDENT_SHARE of the words are
# trusted, such as a fade between two slides, is not used at all. Clean slide text reads in
# the 90s, and the garbled words of a half-faded slide anywhere from 9 to 77.
MIN_WORD_CONFIDENCE = 80
MIN_CONFIDENT_SHARE = 0.5
# Frames are compared at this size, which is enough to tell pictures apart.
COMPARE_SIZE = (64, 36)
# Screen reading is the first half of the progress, transcribing the second.
SCREEN_SHARE = 50

_MARKDOWN_SPECIALS = re.compile(r"([\\`*_\[\]<])")


def _report(percent: int) -> None:
    print(f"\rConverting video ({percent}%)", end="", flush=True)


def _clean(text: str) -> str:
    """One line of the words OCR found, with the one- and no-letter noise lines dropped."""
    lines = [line.strip() for line in text.splitlines()]
    return " / ".join(line for line in lines if sum(c.isalnum() for c in line) >= 2)


def _read_frame(gray) -> str | None:
    """The text on a frame, "" when there is none, or None when Tesseract cannot read it well."""
    data = ocr_data(gray)
    lines: dict[tuple[int, int, int], list[str]] = {}
    seen = confident = 0
    for text, conf, block, paragraph, line in zip(
        data["text"], data["conf"], data["block_num"], data["par_num"], data["line_num"]
    ):
        word = text.strip()
        if not word:
            continue
        seen += 1
        if float(conf) >= MIN_WORD_CONFIDENCE:
            confident += 1
            lines.setdefault((block, paragraph, line), []).append(word)
    if confident < MIN_CONFIDENT_SHARE * seen:
        return None
    return _clean("\n".join(" ".join(words) for words in lines.values()))


def _screen_text(path: Path, should_cancel: Callable[[], bool]) -> list[tuple[float, str]]:
    """The text shown on screen, as (seconds, text) each time it changes."""
    video = cv2.VideoCapture(str(path))
    try:
        fps = video.get(cv2.CAP_PROP_FPS)
        frame_count = video.get(cv2.CAP_PROP_FRAME_COUNT)
        if not video.isOpened() or fps <= 0 or frame_count <= 0:
            raise ValueError("could not read the video's frames")
        duration = frame_count / fps

        shown = []
        last_picture = None
        last_text = ""
        second = 0.0
        while second < duration:
            if should_cancel():
                raise RuntimeError("Cancelled")
            _report(int(SCREEN_SHARE * second / duration))

            video.set(cv2.CAP_PROP_POS_MSEC, second * 1000)
            ok, frame = video.read()
            if not ok:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            picture = cv2.resize(gray, COMPARE_SIZE)
            if last_picture is None or cv2.absdiff(picture, last_picture).mean() >= SAME_PICTURE_DIFF:
                text = _read_frame(gray)
                # A frame Tesseract could not read well changes nothing, so the next one is
                # compared with the last frame that did read, not with this one.
                if text is not None:
                    last_picture = picture
                    same = difflib.SequenceMatcher(None, text.lower(), last_text.lower()).ratio()
                    if text and same < SAME_TEXT_RATIO:
                        shown.append((second, text))
                    last_text = text
            second += FRAME_INTERVAL_SECONDS
        return shown
    finally:
        video.release()


def _speech(
    path: Path, whisper: WhisperModel, should_cancel: Callable[[], bool]
) -> list[tuple[float, str]]:
    """What was said, as (seconds, text) for each stretch of speech Whisper found."""
    segments, info = whisper.transcribe(str(path), vad_filter=True)
    said = []
    for segment in segments:
        if should_cancel():
            raise RuntimeError("Cancelled")
        if segment.text.strip():
            said.append((segment.start, segment.text.strip()))
        if info.duration:
            _report(SCREEN_SHARE + int((100 - SCREEN_SHARE) * segment.end / info.duration))
    return said


def _escape(text: str) -> str:
    """Backslash the characters Markdown would read as emphasis, code, a link or HTML."""
    return _MARKDOWN_SPECIALS.sub(r"\\\1", text)


def _timestamp(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def _timeline(said: list[tuple[float, str]], shown: list[tuple[float, str]]) -> str:
    """Both lists on one timeline. At the same second, the screen comes before the speech."""
    events = [(t, "On screen", text) for t, text in shown] + [(t, "Said", text) for t, text in said]
    events.sort(key=lambda event: event[0])
    return "\n\n".join(f"**{_timestamp(t)}** {label}: {_escape(text)}" for t, label, text in events)


def convert_mp4_to_markdown(
    model: str,
    input_dir: str | Path = INPUT_DIR,
    output_dir: str | Path = OUTPUT_DIR,
    should_cancel: Callable[[], bool] = not_cancelled,
) -> str:
    """Convert all MP4 files in the input folder to Markdown files in the output folder.

    Free and local: Whisper runs on the CPU, Tesseract reads the screen. The Whisper model is
    downloaded from Hugging Face the first time a size is used.

    Args:
        model: Whisper size, one of WHISPER_MODELS.
        input_dir: Folder holding the MP4s.
        output_dir: Folder the Markdown is written to.
        should_cancel: Checked before each frame and each speech segment, true stops the
            file and discards what it had so far.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    if model not in WHISPER_MODELS:
        return f"Error: '{model}' is not a Whisper model. Pick one of: {', '.join(WHISPER_MODELS)}"

    def write(source: Path, dest: Path) -> None:
        # Loaded first, so a model that can't load fails before minutes of screen reading.
        whisper = WhisperModel(model, device="cpu", compute_type="int8")
        shown = _screen_text(source, should_cancel)
        said = _speech(source, whisper, should_cancel)
        print("\rConverting video (100%)")
        if not shown and not said:
            raise ValueError("no speech or on-screen text found")
        dest.write_text(_timeline(said, shown), encoding="utf-8")

    return convert_files(input_dir, output_dir, (".mp4",), (".md",), write, target_label="markdown")


if __name__ == "__main__":
    # Usage: python backend/mp4_md.py <model>
    # There is no default model: without one this exits with a usage message.
    if len(sys.argv) < 2:
        sys.exit(f"Usage: python backend/mp4_md.py <model> (one of: {', '.join(WHISPER_MODELS)})")

    result = convert_mp4_to_markdown(sys.argv[1])
    if not result.startswith("Converted"):
        print(result)
