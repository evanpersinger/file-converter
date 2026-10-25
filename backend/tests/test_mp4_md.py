"""Tests for mp4_md.py, which puts what a video says and shows on one Markdown timeline.

Whisper and Tesseract are faked, so no model is downloaded. The video is real: opencv writes a
tiny one that is white for 3 seconds and then black for 3, so the frame reading is exercised.
"""

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

import mp4_md

WorkDirs = tuple[Path, Path]

Segment = SimpleNamespace
Words = dict[str, list]


def write_video(path: Path, colors: tuple[int, ...] = (255, 0), seconds: int = 3, fps: int = 10) -> Path:
    """Each gray level in `colors` fills the picture for `seconds` seconds, in order."""
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (64, 48))
    for value in colors:
        frame = np.full((48, 64, 3), value, dtype=np.uint8)
        for _ in range(seconds * fps):
            writer.write(frame)
    writer.release()
    return path


def rows(*lines: list[tuple[str, float]]) -> Words:
    """What Tesseract's data output holds for these lines of (word, confidence) pairs, plus
    the empty row with confidence -1 it adds for the page itself."""
    data: Words = {"text": [""], "conf": [-1], "block_num": [1], "par_num": [1], "line_num": [0]}
    for number, line in enumerate(lines, 1):
        for word, confidence in line:
            data["text"].append(word)
            data["conf"].append(confidence)
            data["block_num"].append(1)
            data["par_num"].append(1)
            data["line_num"].append(number)
    return data


def words(text: str, confidence: float = 95) -> Words:
    """`rows` for plain text, one line per line, every word at the same confidence."""
    return rows(*[[(word, confidence) for word in line.split()] for line in text.splitlines()])


class FakeWhisper:
    def __init__(self, segments: list[Segment]) -> None:
        self.segments = segments

    def transcribe(self, path: str, **kwargs: object) -> tuple:
        return iter(self.segments), SimpleNamespace(duration=6.0)


def use_fakes(
    monkeypatch: pytest.MonkeyPatch,
    segments: list[Segment],
    reading: Callable[[np.ndarray], Words],
) -> list[str]:
    """Swap in the fake Whisper and OCR. Returns the model names Whisper is asked to load."""
    loaded: list[str] = []

    def load(model: str, **kwargs: object) -> FakeWhisper:
        loaded.append(model)
        return FakeWhisper(segments)

    monkeypatch.setattr(mp4_md, "WhisperModel", load)
    monkeypatch.setattr(mp4_md, "ocr_data", lambda image, **kwargs: reading(image))
    return loaded


def slide_text(image: np.ndarray) -> str:
    return "SLIDE ONE" if image.mean() > 128 else "SLIDE TWO"


def slide(image: np.ndarray) -> Words:
    return words(slide_text(image))


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(0, "00:00"), (59.9, "00:59"), (61, "01:01"), (3599, "59:59"), (3661, "1:01:01")],
)
def test_timestamps_show_hours_only_when_there_are_some(seconds: float, expected: str) -> None:
    assert mp4_md._timestamp(seconds) == expected


def test_timeline_is_in_time_order_with_the_screen_first_at_the_same_second() -> None:
    timeline = mp4_md._timeline(
        said=[(0.5, "Hello"), (9.0, "Bye")], shown=[(0.0, "Title"), (5.0, "Next")]
    )

    assert timeline == (
        "**00:00** On screen: Title\n\n**00:00** Said: Hello\n\n"
        "**00:05** On screen: Next\n\n**00:09** Said: Bye"
    )


def test_markdown_characters_in_the_text_stay_literal() -> None:
    assert mp4_md._timeline([(0, "a_b *c* [d]")], []) == "**00:00** Said: a\\_b \\*c\\* \\[d\\]"


def test_ocr_noise_lines_are_dropped_and_the_rest_joined() -> None:
    assert mp4_md._clean("Hello\n|\nx\n  World  \n") == "Hello / World"


def test_a_frame_is_read_line_by_line(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mp4_md, "ocr_data", lambda image: words("Title\nBody text"))

    assert mp4_md._read_frame(None) == "Title / Body text"


def test_words_tesseract_is_unsure_of_are_left_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        mp4_md, "ocr_data", lambda image: rows([("Hello", 95), ("w0rld", 30), ("Agenda", 92)])
    )

    assert mp4_md._read_frame(None) == "Hello Agenda"


def test_a_frame_that_is_mostly_unsure_words_cannot_be_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        mp4_md, "ocr_data", lambda image: rows([("hey", 20), ("ce", 15), ("fac", 40), ("Agenda", 90)])
    )

    assert mp4_md._read_frame(None) is None


def test_a_frame_with_no_words_reads_as_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mp4_md, "ocr_data", lambda image: words(""))

    assert mp4_md._read_frame(None) == ""


def test_an_unknown_model_is_refused_before_anything_loads(
    work_dirs: WorkDirs, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, output_dir = work_dirs
    write_video(input_dir / "clip.mp4")
    loaded = use_fakes(monkeypatch, [], slide)

    summary = mp4_md.convert_mp4_to_markdown("gpt-4", input_dir, output_dir)

    assert summary.startswith("Error: 'gpt-4' is not a Whisper model")
    assert loaded == []


def test_speech_and_screen_text_land_on_one_timeline(
    work_dirs: WorkDirs, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, output_dir = work_dirs
    write_video(input_dir / "clip.mp4")
    segments = [
        Segment(start=1.0, end=2.0, text=" Hello there "),
        Segment(start=5.0, end=6.0, text="Goodbye"),
    ]
    loaded = use_fakes(monkeypatch, segments, slide)

    summary = mp4_md.convert_mp4_to_markdown("tiny", input_dir, output_dir)

    assert "clip.md" in summary
    assert loaded == ["tiny"]
    assert (output_dir / "clip.md").read_text(encoding="utf-8") == (
        "**00:00** On screen: SLIDE ONE\n\n**00:01** Said: Hello there\n\n"
        "**00:04** On screen: SLIDE TWO\n\n**00:05** Said: Goodbye"
    )


def test_a_frame_that_looks_like_the_last_one_is_not_read_again(
    work_dirs: WorkDirs, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, output_dir = work_dirs
    write_video(input_dir / "clip.mp4")
    readings: list[str] = []

    def reading(image: np.ndarray) -> Words:
        readings.append(slide_text(image))
        return words(readings[-1])

    use_fakes(monkeypatch, [], reading)

    mp4_md.convert_mp4_to_markdown("tiny", input_dir, output_dir)

    # Frames at 0s, 2s and 4s are sampled, the 2s one is the same white picture as the 0s one.
    assert readings == ["SLIDE ONE", "SLIDE TWO"]


def test_a_slightly_different_reading_of_the_same_screen_is_not_a_new_entry(
    work_dirs: WorkDirs, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, output_dir = work_dirs
    write_video(input_dir / "clip.mp4")
    use_fakes(
        monkeypatch, [],
        lambda image: words(
            "Quarterly Planning Agenda" if image.mean() > 128 else "Quarterly Plannlng Agenda"
        ),
    )

    mp4_md.convert_mp4_to_markdown("tiny", input_dir, output_dir)

    assert (output_dir / "clip.md").read_text(encoding="utf-8") == "**00:00** On screen: Quarterly Planning Agenda"


def test_a_frame_tesseract_cannot_read_well_adds_nothing(
    work_dirs: WorkDirs, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The black frame is the fade between slides: all its words are low confidence."""
    input_dir, output_dir = work_dirs
    write_video(input_dir / "clip.mp4")
    use_fakes(
        monkeypatch, [],
        lambda image: words("SLIDE ONE") if image.mean() > 128 else words("hey ce fac", confidence=20),
    )

    mp4_md.convert_mp4_to_markdown("tiny", input_dir, output_dir)

    assert (output_dir / "clip.md").read_text(encoding="utf-8") == "**00:00** On screen: SLIDE ONE"


def test_a_slide_does_not_repeat_after_an_unreadable_frame_in_the_middle_of_it(
    work_dirs: WorkDirs, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, output_dir = work_dirs
    # White, then a black stretch Tesseract cannot read, then white again. 2.5 seconds keeps the
    # sampled frames off the seconds where the picture changes.
    write_video(input_dir / "clip.mp4", colors=(255, 0, 255))
    monkeypatch.setattr(mp4_md, "FRAME_INTERVAL_SECONDS", 2.5)
    use_fakes(
        monkeypatch, [],
        lambda image: words("SLIDE ONE") if image.mean() > 128 else words("hey ce fac", confidence=20),
    )

    mp4_md.convert_mp4_to_markdown("tiny", input_dir, output_dir)

    assert (output_dir / "clip.md").read_text(encoding="utf-8") == "**00:00** On screen: SLIDE ONE"


def test_a_video_with_nothing_to_read_or_hear_is_reported_as_failed(
    work_dirs: WorkDirs, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, output_dir = work_dirs
    write_video(input_dir / "clip.mp4")
    use_fakes(monkeypatch, [], lambda image: words(""))

    summary = mp4_md.convert_mp4_to_markdown("tiny", input_dir, output_dir)

    assert summary == "No files converted. 1 failed: clip.mp4: no speech or on-screen text found"
    assert not (output_dir / "clip.md").exists()


def test_cancelling_drops_the_file_instead_of_writing_part_of_it(
    work_dirs: WorkDirs, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, output_dir = work_dirs
    write_video(input_dir / "clip.mp4")
    use_fakes(monkeypatch, [Segment(start=1.0, end=2.0, text="Hello")], slide)

    summary = mp4_md.convert_mp4_to_markdown("tiny", input_dir, output_dir, should_cancel=lambda: True)

    assert summary == "No files converted. 1 failed: clip.mp4: Cancelled"
    assert not (output_dir / "clip.md").exists()
