"""Fixtures shared by the converter tests.

The converters take their input and output folders as arguments, so a test hands them a
tmp_path pair (`work_dirs`) and never touches the real backend/input and backend/output.
"""

from collections.abc import Callable
from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture
def work_dirs(tmp_path: Path) -> tuple[Path, Path]:
    """A throwaway (input_dir, output_dir) pair to hand to a converter.

    Only the input directory is created, so a converter making its own output directory
    stays testable.
    """
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    return input_dir, tmp_path / "output"


@pytest.fixture
def write_image() -> Callable[..., Path]:
    """Write a small genuine image, so Pillow has something real to open.

    The format is passed explicitly rather than inferred, so a test can deliberately
    mismatch the contents and the extension.
    """

    def write(path: Path, fmt: str = "JPEG", color: str = "red") -> Path:
        Image.new("RGB", (8, 8), color).save(path, fmt)
        return path

    return write
