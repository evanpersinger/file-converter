"""Shared loop for the converters that turn each file in input/ into one file in output/.

A converter names its source and target extensions and the one step that writes the file.
"""

from collections.abc import Callable
from pathlib import Path

from find_files import find_files

BACKEND_DIR = Path(__file__).resolve().parent
INPUT_DIR = BACKEND_DIR / "input"
OUTPUT_DIR = BACKEND_DIR / "output"


def convert_files(
    input_dir: str | Path,
    output_dir: str | Path,
    source_exts: tuple[str, ...],
    target_exts: tuple[str, ...],
    convert: Callable[[Path, Path], None],
    source_label: str | None = None,
    target_label: str | None = None,
    precheck: Callable[[], str | None] | None = None,
) -> str:
    """Convert every source_exts file in input_dir to a target_exts[0] file in output_dir.

    `convert` gets the source path and the path to write. A file that fails is reported in
    the summary and does not stop the rest of the batch. The labels word the "No X files
    found" and "already in X format" messages, and default to the extensions ("JPG", "jpg").
    `precheck` runs once there are files to convert, and a message it returns (a missing
    tool, say) is returned as the result instead of converting.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    target = target_exts[0].lstrip(".")
    source_label = source_label or source_exts[0].lstrip(".").upper()
    target_label = target_label or target

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    source_files = find_files(input_dir, *source_exts)

    if not source_files:
        if find_files(input_dir, *target_exts):
            return f"That file is already in {target_label} format"
        return f"No {source_label} files found in input folder"

    if precheck and (problem := precheck()):
        return problem

    converted = []
    errors = []

    for source_file in source_files:
        source_name = Path(source_file).name
        try:
            filename = Path(source_file).stem
            target_file = output_dir / f"{filename}.{target}"

            existed_before = target_file.exists()
            print(f"Converting {source_name} to {target}")

            convert(Path(source_file), target_file)
            print(f"Converted {source_name} to {filename}.{target}")
            if existed_before:
                print(f"Overwrote existing file: {filename}.{target}")
            converted.append(f"{filename}.{target}")

        # vtracer is a Rust extension: on input it dislikes it panics, and pyo3's
        # PanicException derives from BaseException, so `except Exception` never sees it and
        # one bad file would take down the whole batch. The class is not importable to name
        # directly, hence the wide catch with the interrupts re-raised first.
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException as e:
            print(f"Error converting {source_file}: {str(e)}")
            errors.append(f"{source_name}: {e}")

    if not converted:
        return f"No files converted. {len(errors)} failed: {'; '.join(errors)}"

    summary = f"Converted {len(converted)} file(s) to output/: {', '.join(converted)}"
    if errors:
        summary += f". {len(errors)} failed: {'; '.join(errors)}"
    return summary
