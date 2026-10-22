"""Shared loop for the Pillow image-to-image converters (jpg_png and friends).

A converter names its source and target extensions and the one step that saves the image.
"""

from collections.abc import Callable
from pathlib import Path

from PIL import Image, ImageSequence

from find_files import find_files

BACKEND_DIR = Path(__file__).resolve().parent
INPUT_DIR = BACKEND_DIR / "input"
OUTPUT_DIR = BACKEND_DIR / "output"


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


def convert_images(
    input_dir: str | Path,
    output_dir: str | Path,
    source_exts: tuple[str, ...],
    target_exts: tuple[str, ...],
    save: Callable[[Image.Image, Path], None],
) -> str:
    """Convert every source_exts file in input_dir to a target_exts[0] file in output_dir.

    `save` gets the opened image and the path to write it to. A file that fails is reported
    in the summary and does not stop the rest of the batch.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    source_label = source_exts[0].lstrip(".").upper()
    target = target_exts[0].lstrip(".")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    source_files = find_files(input_dir, *source_exts)

    if not source_files:
        if find_files(input_dir, *target_exts):
            return f"That file is already in {target} format"
        return f"No {source_label} files found in input folder"

    converted = []
    errors = []

    for source_file in source_files:
        source_name = Path(source_file).name
        try:
            filename = Path(source_file).stem
            target_file = output_dir / f"{filename}.{target}"

            existed_before = target_file.exists()
            print(f"Converting {source_name} to {target}")

            with Image.open(source_file) as img:
                save(img, target_file)
            print(f"Converted {source_name} to {filename}.{target}")
            if existed_before:
                print(f"Overwrote existing file: {filename}.{target}")
            converted.append(f"{filename}.{target}")

        except Exception as e:
            print(f"Error converting {source_file}: {str(e)}")
            errors.append(f"{source_name}: {e}")

    if not converted:
        return f"No files converted. {len(errors)} failed: {'; '.join(errors)}"

    summary = f"Converted {len(converted)} file(s) to output/: {', '.join(converted)}"
    if errors:
        summary += f". {len(errors)} failed: {'; '.join(errors)}"
    return summary
