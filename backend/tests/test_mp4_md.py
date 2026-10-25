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


def write_video(path: Path, fps: int = 10) -> Path:
    """White for the first 3 seconds, black for the next 3."""
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (64, 48))
    for value in (255, 0):
        frame = np.full((48, 64, 3), value, dtype=np.uint8)
        for _ in range(3 * fps):
            writer.write(frame)
    writer.release()
    return path


class FakeWhisper:
    def __init__(self, segments: list[Segment]) -> None:
        self.segments = segments

    def transcribe(self, path: str, **kwargs: object) -> tuple:
        return iter(self.segments), SimpleNamespace(duration=6.0)


def use_fakes(
    monkeypatch: pytest.MonkeyPatch,
    segments: list[Segment],
    reading: Callable[[np.ndarray], str],
) -> list[str]:
    """Swap in the fake Whisper and OCR. Returns the model names Whisper is asked to load."""
    loaded: list[str] = []

    def load(model: str, **kwargs: object) -> FakeWhisper:
        loaded.append(model)
        return FakeWhisper(segments)

    monkeypatch.setattr(mp4_md, "WhisperModel", load)
    monkeypatch.setattr(mp4_md, "ocr_text", lambda image, **kwargs: reading(image))
    return loaded


def slide_text(image: np.ndarray) -> str:
    return "SLIDE ONE" if image.mean() > 128 else "SLIDE TWO"


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


def test_an_unknown_model_is_refused_before_anything_loads(
    work_dirs: WorkDirs, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, output_dir = work_dirs
    write_video(input_dir / "clip.mp4")
    loaded = use_fakes(monkeypatch, [], slide_text)

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
    loaded = use_fakes(monkeypatch, segments, slide_text)

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

    def reading(image: np.ndarray) -> str:
        readings.append(slide_text(image))
        return readings[-1]

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
        lambda image: "Quarterly Planning Agenda" if image.mean() > 128 else "Quarterly Plannlng Agenda",
    )

    mp4_md.convert_mp4_to_markdown("tiny", input_dir, output_dir)

    assert (output_dir / "clip.md").read_text(encoding="utf-8") == "**00:00** On screen: Quarterly Planning Agenda"


def test_a_video_with_nothing_to_read_or_hear_is_reported_as_failed(
    work_dirs: WorkDirs, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, output_dir = work_dirs
    write_video(input_dir / "clip.mp4")
    use_fakes(monkeypatch, [], lambda image: "")

    summary = mp4_md.convert_mp4_to_markdown("tiny", input_dir, output_dir)

    assert summary == "No files converted. 1 failed: clip.mp4: no speech or on-screen text found"
    assert not (output_dir / "clip.md").exists()


def test_cancelling_drops_the_file_instead_of_writing_part_of_it(
    work_dirs: WorkDirs, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, output_dir = work_dirs
    write_video(input_dir / "clip.mp4")
    use_fakes(monkeypatch, [Segment(start=1.0, end=2.0, text="Hello")], slide_text)

    summary = mp4_md.convert_mp4_to_markdown("tiny", input_dir, output_dir, should_cancel=lambda: True)

    assert summary == "No files converted. 1 failed: clip.mp4: Cancelled"
    assert not (output_dir / "clip.md").exists()
