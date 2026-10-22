"""Tests for jpg_svg.py, which traces JPGs into vector paths with vtracer.

The quality of the trace is a tuning question, not a unit-test one, and the module
docstring already explains why a JPEG is a poor source. What is tested here is the
batch contract around vtracer: file discovery, the messages sent back to the caller,
and error isolation.
"""

from collections.abc import Callable
from pathlib import Path

import pytest

import jpg_svg

WorkDirs = tuple[Path, Path]
WriteImage = Callable[..., Path]


def test_reports_when_input_is_empty(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    assert (
        jpg_svg.convert_jpg_to_svg(input_dir, output_dir) == "No JPG files found in input folder"
    )


def test_reports_when_the_file_is_already_an_svg(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "logo.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>')

    assert (
        jpg_svg.convert_jpg_to_svg(input_dir, output_dir) == "That file is already in svg format"
    )


def test_traces_a_single_jpg(work_dirs: WorkDirs, write_image: WriteImage) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / "logo.jpg")

    summary = jpg_svg.convert_jpg_to_svg(input_dir, output_dir)

    assert "logo.svg" in summary
    assert (output_dir / "logo.svg").read_text().lstrip().startswith("<?xml")


def test_the_traced_output_contains_vector_paths(
    work_dirs: WorkDirs, write_image: WriteImage
) -> None:
    """A tracer that silently emitted an empty canvas would still pass every other
    test here, since the file would exist and parse."""
    input_dir, output_dir = work_dirs
    write_image(input_dir / "logo.jpg")

    jpg_svg.convert_jpg_to_svg(input_dir, output_dir)

    svg = (output_dir / "logo.svg").read_text()
    assert "<svg" in svg
    assert "<path" in svg


@pytest.mark.parametrize("filename", ["logo.jpg", "logo.jpeg", "logo.JPG", "logo.JPEG"])
def test_picks_up_every_spelling_of_the_extension(
    work_dirs: WorkDirs, write_image: WriteImage, filename: str
) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / filename)

    jpg_svg.convert_jpg_to_svg(input_dir, output_dir)

    assert (output_dir / "logo.svg").exists()


def test_a_file_is_traced_exactly_once(work_dirs: WorkDirs, write_image: WriteImage) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / "logo.jpg")

    summary = jpg_svg.convert_jpg_to_svg(input_dir, output_dir)

    assert summary.count("logo.svg") == 1
    assert len(list(output_dir.iterdir())) == 1


def test_traces_several_files(work_dirs: WorkDirs, write_image: WriteImage) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / "one.jpg")
    write_image(input_dir / "two.jpg", color="blue")

    summary = jpg_svg.convert_jpg_to_svg(input_dir, output_dir)

    assert "Converted 2 file(s)" in summary
    assert sorted(p.name for p in output_dir.iterdir()) == ["one.svg", "two.svg"]


def test_an_unreadable_file_is_reported_rather_than_raised(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "broken.jpg").write_bytes(b"this is not a jpeg")

    summary = jpg_svg.convert_jpg_to_svg(input_dir, output_dir)

    assert summary.startswith("No files converted. 1 failed:")
    assert "broken.jpg" in summary


def test_one_bad_file_does_not_stop_the_good_ones(
    work_dirs: WorkDirs, write_image: WriteImage
) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / "good.jpg")
    (input_dir / "broken.jpg").write_bytes(b"this is not a jpeg")

    summary = jpg_svg.convert_jpg_to_svg(input_dir, output_dir)

    assert "good.svg" in summary
    assert "1 failed" in summary
    assert (output_dir / "good.svg").exists()


def test_output_folder_is_created_when_missing(
    work_dirs: WorkDirs, write_image: WriteImage
) -> None:
    input_dir, output_dir = work_dirs
    assert not output_dir.exists()
    write_image(input_dir / "logo.jpg")

    jpg_svg.convert_jpg_to_svg(input_dir, output_dir)

    assert output_dir.is_dir()
