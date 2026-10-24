"""Pillow helpers for the image converters (jpg_png, jpg_pdf, webp_svg and friends).

Builds on batch_convert: each converter names its extensions and the step that saves.
"""

from collections.abc import Callable
from pathlib import Path

from PIL import Image, ImageOps, ImageSequence

from batch_convert import convert_files


def saver(fmt: str, **options) -> Callable[[Image.Image, Path], None]:
    """A `save` for convert_images that writes the image as `fmt`, passing options to Pillow."""

    def save(img: Image.Image, dest: Path) -> None:
        img.save(dest, fmt, **options)

    return save


def _flatten_on_white(frame: Image.Image) -> Image.Image:
    """Return the frame as an RGB image with any transparency painted white."""
    rgba = frame.convert("RGBA")
    page = Image.new("RGB", rgba.size, "white")
    page.paste(rgba, mask=rgba.getchannel("A"))
    return page


def save_jpg_on_white(img: Image.Image, dest: Path) -> None:
    """A `save` for convert_images that writes a JPG, painting any transparency white."""
    _flatten_on_white(img).save(dest, "JPEG", quality=95)


def save_pdf(img: Image.Image, dest: Path) -> None:
    """A `save` for convert_images that writes a one-page PDF at 100 DPI."""
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.save(dest, "PDF", resolution=100.0)


def save_pdf_pages(img: Image.Image, dest: Path) -> None:
    """A `save` for convert_images that writes a PDF with one page per frame, each frame
    flattened onto white. A still image gives a single page."""
    pages = [_flatten_on_white(frame) for frame in ImageSequence.Iterator(img)]
    pages[0].save(dest, "PDF", save_all=True, append_images=pages[1:], resolution=100.0)


def upright(img: Image.Image) -> Image.Image:
    """Apply the EXIF orientation tag, so a phone photo stored rotated comes out the
    right way up. An image with no orientation to apply is returned as is, since
    exif_transpose would hand back a copy that loses an animation's other frames."""
    if img.getexif().get(0x0112, 1) == 1:
        return img
    return ImageOps.exif_transpose(img)


def convert_images(
    input_dir: str | Path,
    output_dir: str | Path,
    source_exts: tuple[str, ...],
    target_exts: tuple[str, ...],
    save: Callable[[Image.Image, Path], None],
    source_label: str | None = None,
    target_label: str | None = None,
) -> str:
    """convert_files for Pillow images: `save` gets the opened image and the path to write."""

    def convert(source: Path, dest: Path) -> None:
        with Image.open(source) as img:
            save(upright(img), dest)

    return convert_files(
        input_dir, output_dir, source_exts, target_exts, convert, source_label, target_label
    )
