"""Tests for csv_md.py."""

from pathlib import Path

import csv_md


def _convert(tmp_path: Path, raw: bytes) -> str:
    source = tmp_path / "t.csv"
    source.write_bytes(raw)
    return csv_md.csv_to_markdown(source)


def test_empty_file_gives_empty_string(tmp_path: Path) -> None:
    assert _convert(tmp_path, b"") == ""


def test_basic_table(tmp_path: Path) -> None:
    assert _convert(tmp_path, b"a,b\n1,2\n") == "| a | b |\n| --- | --- |\n| 1 | 2 |\n"


def test_bom_does_not_leak_into_first_header(tmp_path: Path) -> None:
    assert _convert(tmp_path, b"\xef\xbb\xbfname,note\na,b\n").startswith("| name | note |")


def test_pipe_in_a_cell_is_escaped(tmp_path: Path) -> None:
    assert "| a\\|b | c |" in _convert(tmp_path, b"x,y\na|b,c\n")


def test_newline_in_a_cell_becomes_br(tmp_path: Path) -> None:
    assert "| line1<br>line2 |" in _convert(tmp_path, b'x\n"line1\nline2"\n')


def test_short_rows_are_padded(tmp_path: Path) -> None:
    assert _convert(tmp_path, b"name,note\nshort\n").splitlines()[-1] == "| short |  |"
