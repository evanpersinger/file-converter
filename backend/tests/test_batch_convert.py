"""Tests for batch_convert.py, the loop the one-file-in, one-file-out converters share."""

from pathlib import Path

from batch_convert import convert_files

WorkDirs = tuple[Path, Path]


def copy_unless_bad(source: Path, dest: Path) -> None:
    content = source.read_bytes()
    if content == b"bad":
        raise ValueError("cannot read this")
    dest.write_bytes(content)


def run(work_dirs: WorkDirs) -> str:
    input_dir, output_dir = work_dirs
    return convert_files(input_dir, output_dir, (".txt",), (".md",), copy_unless_bad)


def test_reports_when_input_is_empty(work_dirs: WorkDirs) -> None:
    assert run(work_dirs) == "No TXT files found in input folder"


def test_reports_when_the_file_is_already_in_the_target_format(work_dirs: WorkDirs) -> None:
    input_dir, _ = work_dirs
    (input_dir / "notes.md").write_text("done")

    assert run(work_dirs) == "That file is already in md format"


def test_one_bad_file_does_not_stop_the_good_ones(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "good.txt").write_bytes(b"fine")
    (input_dir / "broken.txt").write_bytes(b"bad")

    summary = run(work_dirs)

    assert "good.md" in summary
    assert "1 failed" in summary
    assert "broken.txt" in summary
    assert (output_dir / "good.md").exists()


def test_an_existing_output_file_is_overwritten(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "notes.txt").write_bytes(b"new")
    output_dir.mkdir()
    (output_dir / "notes.md").write_bytes(b"stale")

    run(work_dirs)

    assert (output_dir / "notes.md").read_bytes() == b"new"


def test_the_output_folder_is_created_when_missing(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "notes.txt").write_bytes(b"text")
    assert not output_dir.exists()

    run(work_dirs)

    assert (output_dir / "notes.md").exists()
