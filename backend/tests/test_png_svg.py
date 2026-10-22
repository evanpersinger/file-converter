"""Tests for png_svg.py, which traces PNGs into vector paths with vtracer.

The same batch contract as jpg_svg.py, against a source format that actually suits
tracing. The error-isolation cases matter most here: this module makes the same
vtracer call, which panics rather than raising on an unreadable file.
"""

from collections.abc import Callable
from pathlib import Path

import pytest

import png_svg

WorkDirs = tuple[Path, Path]
WriteImage = Callable[..., Path]


def test_reports_when_input_is_empty(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    assert (
        png_svg.convert_png_to_svg(input_dir, output_dir) == "No PNG files found in input folder"
    )


def test_reports_when_the_file_is_already_an_svg(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "logo.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>')

    assert (
        png_svg.convert_png_to_svg(input_dir, output_dir) == "That file is already in svg format"
    )


def test_traces_a_single_png(work_dirs: WorkDirs, write_image: WriteImage) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / "logo.png", "PNG")

    summary = png_svg.convert_png_to_svg(input_dir, output_dir)

    assert "logo.svg" in summary
    svg = (output_dir / "logo.svg").read_text()
    assert "<svg" in svg
    assert "<path" in svg


@pytest.mark.parametrize("filename", ["logo.png", "logo.PNG"])
def test_picks_up_both_spellings_of_the_extension(
    work_dirs: WorkDirs, write_image: WriteImage, filename: str
) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / filename, "PNG")

    png_svg.convert_png_to_svg(input_dir, output_dir)

    assert (output_dir / "logo.svg").exists()


def test_a_file_is_traced_exactly_once(work_dirs: WorkDirs, write_image: WriteImage) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / "logo.png", "PNG")

    summary = png_svg.convert_png_to_svg(input_dir, output_dir)

    assert summary.count("logo.svg") == 1
    assert len(list(output_dir.iterdir())) == 1


def test_traces_several_files(work_dirs: WorkDirs, write_image: WriteImage) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / "one.png", "PNG")
    write_image(input_dir / "two.png", "PNG", color="blue")

    summary = png_svg.convert_png_to_svg(input_dir, output_dir)

    assert "Converted 2 file(s)" in summary
    assert sorted(p.name for p in output_dir.iterdir()) == ["one.svg", "two.svg"]


def test_an_unreadable_file_is_reported_rather_than_raised(work_dirs: WorkDirs) -> None:
    """vtracer panics on this rather than raising, and pyo3's PanicException does not
    derive from Exception. Without the wide catch the whole batch dies here."""
    input_dir, output_dir = work_dirs
    (input_dir / "broken.png").write_bytes(b"this is not a png")

    summary = png_svg.convert_png_to_svg(input_dir, output_dir)

    assert summary.startswith("No files converted. 1 failed:")
    assert "broken.png" in summary


def test_one_bad_file_does_not_stop_the_good_ones(
    work_dirs: WorkDirs, write_image: WriteImage
) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / "good.png", "PNG")
    (input_dir / "broken.png").write_bytes(b"this is not a png")

    summary = png_svg.convert_png_to_svg(input_dir, output_dir)

    assert "good.svg" in summary
    assert "1 failed" in summary
    assert (output_dir / "good.svg").exists()


def test_output_folder_is_created_when_missing(
    work_dirs: WorkDirs, write_image: WriteImage
) -> None:
    input_dir, output_dir = work_dirs
    assert not output_dir.exists()
    write_image(input_dir / "logo.png", "PNG")

    png_svg.convert_png_to_svg(input_dir, output_dir)

    assert output_dir.is_dir()


def test_transparency_does_not_break_the_trace(work_dirs: WorkDirs) -> None:
    """PNG carries an alpha channel and JPG does not, so this is the one input shape
    png_svg can be handed that jpg_svg never sees."""
    from PIL import Image

    input_dir, output_dir = work_dirs
    Image.new("RGBA", (8, 8), (255, 0, 0, 128)).save(input_dir / "clear.png", "PNG")

    summary = png_svg.convert_png_to_svg(input_dir, output_dir)

    assert "clear.svg" in summary
    assert "<svg" in (output_dir / "clear.svg").read_text()
