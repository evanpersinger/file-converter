from pathlib import Path

from find_files import find_files


def _names(paths: list[str]) -> set[str]:
    return {Path(p).name for p in paths}


def test_matches_the_extension_in_any_case(tmp_path: Path) -> None:
    for name in ("a.csv", "B.CSV", "c.Csv", "d.txt"):
        (tmp_path / name).touch()

    assert _names(find_files(tmp_path, ".csv")) == {"a.csv", "B.CSV", "c.Csv"}


def test_matches_any_of_several_extensions(tmp_path: Path) -> None:
    for name in ("a.jpg", "b.JPEG", "c.png"):
        (tmp_path / name).touch()

    assert _names(find_files(tmp_path, ".jpg", ".jpeg")) == {"a.jpg", "b.JPEG"}


def test_skips_hidden_files_and_directories(tmp_path: Path) -> None:
    (tmp_path / "._a.csv").touch()
    (tmp_path / "dir.csv").mkdir()
    (tmp_path / "real.csv").touch()

    assert _names(find_files(tmp_path, ".csv")) == {"real.csv"}


def test_missing_folder_gives_an_empty_list(tmp_path: Path) -> None:
    assert find_files(tmp_path / "nope", ".csv") == []
