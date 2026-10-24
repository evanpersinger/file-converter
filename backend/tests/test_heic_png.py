"""Tests for heic_png.py, which writes each HEIC to a PNG and keeps its transparency."""

from collections.abc import Callable
from pathlib import Path

import pytest
from PIL import Image

import heic_png

WorkDirs = tuple[Path, Path]
WriteImage = Callable[..., Path]


@pytest.mark.parametrize("filename", ["photo.heic", "photo.HEIC"])
def test_a_heic_becomes_a_png(
    work_dirs: WorkDirs, write_image: WriteImage, filename: str
) -> None:
    input_dir, output_dir = work_dirs
    write_image(input_dir / filename, "HEIF")

    summary = heic_png.convert_heic_to_png(input_dir, output_dir)

    assert "photo.png" in summary
    with Image.open(output_dir / "photo.png") as converted:
        assert converted.format == "PNG"


def test_transparent_areas_stay_transparent(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    Image.new("RGBA", (40, 40), (0, 0, 0, 0)).save(input_dir / "clear.heic", "HEIF")

    heic_png.convert_heic_to_png(input_dir, output_dir)

    with Image.open(output_dir / "clear.png") as converted:
        assert converted.mode == "RGBA"
        assert converted.getpixel((2, 2))[3] < 10
