"""Downscale the raster images inside an Office Open XML zip (.pptx/.docx/.xlsx).

Office Open XML formats are zip archives; the XML text inside is a few KB, embedded
pictures are what make a file large. Safe to call only when the caller's output never
depends on those image bytes (pptx_md, for example, only ever reads shape text). This
module never touches anything outside `media_prefix`, and any failure leaves the file
exactly as it was, so a caller for which that safety argument doesn't hold (anything
that renders images into its output) must not call it.
"""

import io
import zipfile
from pathlib import Path
from typing import Callable

from PIL import Image

# Left untouched: vector formats have no pixels to downscale, and re-encoding an
# animated image would drop every frame but the first.
_SKIP_SUFFIXES = {".emf", ".wmf", ".svg"}

# Longest side a media image is allowed to keep after downscaling. Chosen so
# Tesseract still reads text-in-picture at this size, see test_compress.py.
_MAX_DIMENSION = 1600

_JPEG_QUALITY = 85


def has_compressible_media(path: Path, media_prefix: str) -> bool:
    """Whether `path` has a raster image under `media_prefix` worth downscaling.

    A cheap directory-only scan, so a caller can skip the full compress+sanity-check
    pass entirely for a file with nothing to shrink.
    """
    with zipfile.ZipFile(path) as archive:
        return any(
            name.startswith(media_prefix) and Path(name).suffix.lower() not in _SKIP_SUFFIXES
            for name in archive.namelist()
        )


def _downscale(data: bytes) -> bytes:
    """Return `data` re-encoded smaller, or `data` unchanged if that isn't safe or
    doesn't help."""
    with Image.open(io.BytesIO(data)) as img:
        if getattr(img, "is_animated", False) or max(img.size) <= _MAX_DIMENSION:
            return data
        img.thumbnail((_MAX_DIMENSION, _MAX_DIMENSION), Image.LANCZOS)
        out = io.BytesIO()
        save_kwargs = {"quality": _JPEG_QUALITY} if img.format == "JPEG" else {}
        img.save(out, format=img.format, **save_kwargs)
        smaller = out.getvalue()
    return smaller if len(smaller) < len(data) else data


def compress_office_zip(
    path: Path,
    media_prefix: str,
    sanity_check: Callable[[bytes], None],
) -> None:
    """Downscale every raster image under `media_prefix` inside the zip at `path`, in
    place.

    `sanity_check(payload)` must raise if `payload` is no longer a valid file for
    whatever format this is, e.g. `lambda p: Presentation(io.BytesIO(p))` for a pptx.
    Rebuilds the archive in memory and only overwrites `path` if every step succeeds,
    non-media entries stay byte-for-byte identical, and `sanity_check` passes. Any
    failure (an image Pillow can't decode, a corrupt entry, a failed sanity check)
    leaves `path` exactly as it was, deliberately caught broadly since a compression
    bug must never break a conversion that would have worked on the original file.
    """
    try:
        rebuilt = io.BytesIO()
        with zipfile.ZipFile(path) as original, \
                zipfile.ZipFile(rebuilt, "w", zipfile.ZIP_DEFLATED) as archive:
            for info in original.infolist():
                data = original.read(info.filename)
                suffix = Path(info.filename).suffix.lower()
                if info.filename.startswith(media_prefix) and suffix not in _SKIP_SUFFIXES:
                    data = _downscale(data)
                archive.writestr(info, data)

        payload = rebuilt.getvalue()
        sanity_check(payload)
    except Exception:
        return

    path.write_bytes(payload)
