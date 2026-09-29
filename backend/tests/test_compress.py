"""Tests for compress.py.

Builds bare zips in-test (no real .pptx needed) since compress_office_zip only cares
about zip entries and a media prefix, not any particular Office format.
"""

import io
import random
import zipfile
from pathlib import Path

from PIL import Image

import compress


def _write_zip(path: Path, entries: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)


def _big_jpeg() -> bytes:
    # Random noise, not a solid color: a flat-color JPEG is already tiny at any
    # resolution, so it wouldn't shrink when downscaled and this test would be
    # asserting nothing.
    rng = random.Random(0)
    size = (2000, 1200)
    img = Image.new("RGB", size)
    img.putdata([(rng.randrange(256), rng.randrange(256), rng.randrange(256))
                 for _ in range(size[0] * size[1])])
    out = io.BytesIO()
    img.save(out, "JPEG", quality=95)
    return out.getvalue()


def _noop_sanity_check(payload: bytes) -> None:
    pass


def test_downscales_a_large_media_image(tmp_path: Path) -> None:
    path = tmp_path / "deck.pptx"
    _write_zip(path, {
        "[Content_Types].xml": b"<Types/>",
        "ppt/media/image1.jpg": _big_jpeg(),
    })
    before = path.stat().st_size

    compress.compress_office_zip(path, "ppt/media/", _noop_sanity_check)

    assert path.stat().st_size < before
    with zipfile.ZipFile(path) as archive:
        img = Image.open(io.BytesIO(archive.read("ppt/media/image1.jpg")))
        assert max(img.size) <= compress._MAX_DIMENSION


def test_non_media_entries_stay_byte_identical(tmp_path: Path) -> None:
    path = tmp_path / "deck.pptx"
    xml = b"<Types>some xml content that must not change</Types>"
    _write_zip(path, {
        "[Content_Types].xml": xml,
        "ppt/media/image1.jpg": _big_jpeg(),
    })

    compress.compress_office_zip(path, "ppt/media/", _noop_sanity_check)

    with zipfile.ZipFile(path) as archive:
        assert archive.read("[Content_Types].xml") == xml


def test_small_image_is_left_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "deck.pptx"
    small = io.BytesIO()
    Image.new("RGB", (100, 100), "blue").save(small, "JPEG")
    small_bytes = small.getvalue()
    _write_zip(path, {"ppt/media/image1.jpg": small_bytes})

    compress.compress_office_zip(path, "ppt/media/", _noop_sanity_check)

    with zipfile.ZipFile(path) as archive:
        assert archive.read("ppt/media/image1.jpg") == small_bytes


def test_vector_image_is_left_untouched(tmp_path: Path) -> None:
    path = tmp_path / "deck.pptx"
    svg = b"<svg><rect width='9999' height='9999'/></svg>"
    _write_zip(path, {"ppt/media/image1.svg": svg})

    compress.compress_office_zip(path, "ppt/media/", _noop_sanity_check)

    with zipfile.ZipFile(path) as archive:
        assert archive.read("ppt/media/image1.svg") == svg


def test_failed_sanity_check_leaves_file_untouched(tmp_path: Path) -> None:
    path = tmp_path / "deck.pptx"
    _write_zip(path, {"ppt/media/image1.jpg": _big_jpeg()})
    original = path.read_bytes()

    def always_fails(payload: bytes) -> None:
        raise ValueError("not a valid deck")

    compress.compress_office_zip(path, "ppt/media/", always_fails)

    assert path.read_bytes() == original


def test_corrupt_zip_leaves_file_untouched(tmp_path: Path) -> None:
    path = tmp_path / "deck.pptx"
    path.write_bytes(b"not actually a zip file")

    compress.compress_office_zip(path, "ppt/media/", _noop_sanity_check)

    assert path.read_bytes() == b"not actually a zip file"


def test_has_compressible_media_true_for_raster_image(tmp_path: Path) -> None:
    path = tmp_path / "deck.pptx"
    _write_zip(path, {"ppt/media/image1.jpg": _big_jpeg()})
    assert compress.has_compressible_media(path, "ppt/media/") is True


def test_has_compressible_media_false_with_no_media(tmp_path: Path) -> None:
    path = tmp_path / "deck.pptx"
    _write_zip(path, {"[Content_Types].xml": b"<Types/>"})
    assert compress.has_compressible_media(path, "ppt/media/") is False


def test_has_compressible_media_false_for_vector_only(tmp_path: Path) -> None:
    path = tmp_path / "deck.pptx"
    _write_zip(path, {"ppt/media/image1.svg": b"<svg/>"})
    assert compress.has_compressible_media(path, "ppt/media/") is False
