"""Tests for compress.py.

Builds bare zips in-test (no real .pptx needed) since compress_office_zip only cares
about zip entries and a media prefix, not any particular Office format.
"""

import io
import random
import shutil
import zipfile
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

import compress
from external_tool import ocr_text

needs_tesseract = pytest.mark.skipif(
    shutil.which("tesseract") is None, reason="tesseract is not installed"
)


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


def test_a_transparent_png_keeps_its_transparency(tmp_path: Path) -> None:
    # Noise, so the downscaled copy is smaller and actually gets written. The left half is
    # fully transparent, the right half opaque.
    size = (2000, 1200)
    picture = Image.frombytes("RGB", size, random.Random(0).randbytes(size[0] * size[1] * 3))
    picture = picture.convert("RGBA")
    picture.paste(0, (0, 0, size[0] // 2, size[1]))
    buffer = io.BytesIO()
    picture.save(buffer, "PNG")
    path = tmp_path / "deck.pptx"
    _write_zip(path, {"ppt/media/image1.png": buffer.getvalue()})

    compress.compress_office_zip(path, "ppt/media/", _noop_sanity_check)

    with zipfile.ZipFile(path) as archive:
        shrunk = Image.open(io.BytesIO(archive.read("ppt/media/image1.png")))
        shrunk.load()
    assert max(shrunk.size) <= compress._MAX_DIMENSION
    assert shrunk.mode == "RGBA"
    assert shrunk.getpixel((0, 0))[3] == 0
    assert shrunk.getpixel((shrunk.width - 1, 0))[3] == 255


def test_an_animated_gif_is_left_untouched(tmp_path: Path) -> None:
    # Re-encoding would drop every frame but the first. Noise frames, so the downscaled
    # copy would be smaller and written if the animation weren't skipped.
    size = (2000, 1200)
    frames = [
        Image.frombytes("RGB", size, random.Random(seed).randbytes(size[0] * size[1] * 3))
        for seed in (0, 1)
    ]
    buffer = io.BytesIO()
    frames[0].save(buffer, "GIF", save_all=True, append_images=frames[1:])
    gif = buffer.getvalue()
    path = tmp_path / "deck.pptx"
    _write_zip(path, {"ppt/media/image1.gif": gif})

    compress.compress_office_zip(path, "ppt/media/", _noop_sanity_check)

    with zipfile.ZipFile(path) as archive:
        assert archive.read("ppt/media/image1.gif") == gif


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


@needs_tesseract
def test_text_in_a_downscaled_picture_still_reads_the_same(tmp_path: Path) -> None:
    # A 4K screenshot of a slide, with body-sized text, is the case the cap has to survive
    original = Image.new("RGB", (3840, 2160), "white")
    ImageDraw.Draw(original).text(
        (200, 900), "Quarterly revenue report", fill="black",
        font=ImageFont.load_default(size=50),
    )
    buffer = io.BytesIO()
    original.save(buffer, "PNG")
    path = tmp_path / "deck.pptx"
    _write_zip(path, {"ppt/media/image1.png": buffer.getvalue()})

    compress.compress_office_zip(path, "ppt/media/", _noop_sanity_check)

    with zipfile.ZipFile(path) as archive:
        shrunk = Image.open(io.BytesIO(archive.read("ppt/media/image1.png")))
        shrunk.load()
    assert max(shrunk.size) <= compress._MAX_DIMENSION
    before = " ".join(ocr_text(original).lower().split())
    after = " ".join(ocr_text(shrunk).lower().split())
    assert "quarterly revenue report" in before
    assert after == before
