"""Tests for json_toon.py and toon_json.py.

The batch contract is the same shape as the other converters. What is specific here is
fidelity: TOON writes a uniform array of objects as a table and everything else in a
longer form, so the round-trip group at the bottom pushes each shape of JSON through to
TOON and back and compares.
"""

import json
import shutil
from pathlib import Path

import pytest

import json_toon
import toon_json

WorkDirs = tuple[Path, Path]


def round_trip(work_dirs: WorkDirs, data: object) -> object:
    """Send JSON through json_toon and back through toon_json, returning the data that
    comes out the far end. Both legs share the same two folders, so the intermediate
    TOON file is moved from output back to input between them."""
    input_dir, output_dir = work_dirs

    (input_dir / "data.json").write_text(json.dumps(data), encoding="utf-8")
    json_toon.convert_json_to_toon(input_dir, output_dir)

    (input_dir / "data.json").unlink()
    shutil.move(output_dir / "data.toon", input_dir / "data.toon")
    toon_json.convert_toon_to_json(input_dir, output_dir)

    return json.loads((output_dir / "data.json").read_text(encoding="utf-8"))


# json_toon: batch contract


def test_json_toon_reports_when_input_is_empty(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    assert (
        json_toon.convert_json_to_toon(input_dir, output_dir)
        == "No JSON files found in input folder"
    )


def test_json_toon_reports_when_the_file_is_already_toon(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "data.toon").write_text("a: 1\n", encoding="utf-8")

    assert (
        json_toon.convert_json_to_toon(input_dir, output_dir)
        == "That file is already in TOON format"
    )


def test_a_uniform_array_is_written_as_a_toon_table(work_dirs: WorkDirs) -> None:
    """The reason to use TOON at all: the keys are written once, not once per row."""
    input_dir, output_dir = work_dirs
    data = {"users": [{"id": 1, "name": "Ana"}, {"id": 2, "name": "Bo"}]}
    (input_dir / "data.json").write_text(json.dumps(data), encoding="utf-8")

    summary = json_toon.convert_json_to_toon(input_dir, output_dir)

    assert "data.toon" in summary
    assert (output_dir / "data.toon").read_text(encoding="utf-8") == (
        "users[2]{id,name}:\n  1,Ana\n  2,Bo\n"
    )


def test_converts_several_json_files(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "one.json").write_text('{"a": 1}', encoding="utf-8")
    (input_dir / "two.json").write_text('{"b": 2}', encoding="utf-8")

    summary = json_toon.convert_json_to_toon(input_dir, output_dir)

    assert "Converted 2 file(s)" in summary
    assert sorted(p.name for p in output_dir.iterdir()) == ["one.toon", "two.toon"]


def test_invalid_json_is_reported_rather_than_raised(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "broken.json").write_text('{"a": ', encoding="utf-8")

    summary = json_toon.convert_json_to_toon(input_dir, output_dir)

    assert summary.startswith("No files converted. 1 failed:")
    assert "broken.json" in summary
    assert not (output_dir / "broken.toon").exists()


def test_nan_is_rejected_instead_of_silently_becoming_null(work_dirs: WorkDirs) -> None:
    """Python's json module reads NaN and Infinity, and TOON would write them as null,
    which is a different file from the one the user gave."""
    input_dir, output_dir = work_dirs
    (input_dir / "bad.json").write_text('{"v": NaN}', encoding="utf-8")

    summary = json_toon.convert_json_to_toon(input_dir, output_dir)

    assert "NaN is not valid JSON" in summary
    assert not (output_dir / "bad.toon").exists()


def test_one_bad_json_file_does_not_stop_the_good_ones(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "good.json").write_text('{"a": 1}', encoding="utf-8")
    (input_dir / "bad.json").write_text("not json", encoding="utf-8")

    summary = json_toon.convert_json_to_toon(input_dir, output_dir)

    assert "good.toon" in summary
    assert "1 failed" in summary
    assert (output_dir / "good.toon").exists()


def test_a_json_file_with_a_byte_order_mark_is_read(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "bom.json").write_bytes(b"\xef\xbb\xbf" + b'{"a": 1}')

    json_toon.convert_json_to_toon(input_dir, output_dir)

    assert (output_dir / "bom.toon").read_text(encoding="utf-8") == "a: 1\n"


# toon_json: batch contract


def test_toon_json_reports_when_input_is_empty(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    assert (
        toon_json.convert_toon_to_json(input_dir, output_dir)
        == "No TOON files found in input folder"
    )


def test_toon_json_reports_when_the_file_is_already_json(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "data.json").write_text("{}", encoding="utf-8")

    assert (
        toon_json.convert_toon_to_json(input_dir, output_dir)
        == "That file is already in JSON format"
    )


def test_a_toon_table_becomes_an_array_of_objects(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "data.toon").write_text("users[2]{id,name}:\n  1,Ana\n  2,Bo\n", encoding="utf-8")

    summary = toon_json.convert_toon_to_json(input_dir, output_dir)

    assert "data.json" in summary
    assert json.loads((output_dir / "data.json").read_text(encoding="utf-8")) == {
        "users": [{"id": 1, "name": "Ana"}, {"id": 2, "name": "Bo"}]
    }


def test_the_json_is_indented_and_keeps_unicode_readable(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "data.toon").write_text("name: café\n", encoding="utf-8")

    toon_json.convert_toon_to_json(input_dir, output_dir)

    assert (output_dir / "data.json").read_text(encoding="utf-8") == '{\n  "name": "café"\n}\n'


def test_an_empty_toon_file_becomes_an_empty_object(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "empty.toon").write_text("", encoding="utf-8")

    toon_json.convert_toon_to_json(input_dir, output_dir)

    assert json.loads((output_dir / "empty.json").read_text(encoding="utf-8")) == {}


def test_malformed_toon_is_reported_rather_than_raised(work_dirs: WorkDirs) -> None:
    """The table says two rows and has one, which the library refuses to guess about."""
    input_dir, output_dir = work_dirs
    (input_dir / "broken.toon").write_text("users[2]{id,name}:\n  1,Ana\n", encoding="utf-8")

    summary = toon_json.convert_toon_to_json(input_dir, output_dir)

    assert summary.startswith("No files converted. 1 failed:")
    assert "Declared length 2 but found 1" in summary
    assert not (output_dir / "broken.json").exists()


def test_one_bad_toon_file_does_not_stop_the_good_ones(work_dirs: WorkDirs) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "good.toon").write_text("a: 1\n", encoding="utf-8")
    (input_dir / "bad.toon").write_text('key: "unterminated', encoding="utf-8")

    summary = toon_json.convert_toon_to_json(input_dir, output_dir)

    assert "good.json" in summary
    assert "1 failed" in summary
    assert (output_dir / "good.json").exists()


# Round-trip fidelity


@pytest.mark.parametrize(
    "data",
    [
        pytest.param({"users": [{"id": 1, "name": "Ana"}, {"id": 2, "name": "Bo"}]}, id="uniform-table"),
        pytest.param([{"x": 1, "y": 2}, {"x": 3, "y": 4}], id="top-level-table"),
        pytest.param({"items": [{"a": 1}, {"b": 2, "c": [1, 2]}, 3, "x"]}, id="irregular-array"),
        pytest.param({"a": {"b": {"c": [1, [2, 3], {"d": None}]}}}, id="deeply-nested"),
        pytest.param({"name": "café 中文", "emoji": "😀"}, id="unicode"),
        pytest.param(
            {"s": "a,b", "t": "line1\nline2", "u": " padded ", "v": "true", "w": "123", "x": ""},
            id="strings-that-need-quoting",
        ),
        pytest.param({"a b": 1, "a-b": 2, "1": 3}, id="awkward-keys"),
        pytest.param({"big": 10**20, "small": 1e-7, "neg": -5, "pi": 1.5}, id="numbers"),
        pytest.param({"yes": True, "no": False, "nothing": None}, id="booleans-and-null"),
        pytest.param({}, id="empty-object"),
        pytest.param([], id="empty-array"),
        pytest.param(42, id="top-level-number"),
        pytest.param("hello", id="top-level-string"),
        pytest.param(None, id="top-level-null"),
    ],
)
def test_json_survives_the_round_trip(work_dirs: WorkDirs, data: object) -> None:
    assert round_trip(work_dirs, data) == data


def test_key_order_survives_the_round_trip(work_dirs: WorkDirs) -> None:
    result = round_trip(work_dirs, {"z": 1, "a": 2, "m": 3})

    assert list(result) == ["z", "a", "m"]


def test_a_float_with_a_whole_value_comes_back_as_an_integer(work_dirs: WorkDirs) -> None:
    """TOON writes 1.0 as 1. The number is the same, but the text 1.0 is not kept, so a
    consumer that cares about the float/int difference sees it change."""
    input_dir, output_dir = work_dirs
    (input_dir / "data.json").write_text('{"a": 1.0}', encoding="utf-8")
    json_toon.convert_json_to_toon(input_dir, output_dir)

    assert (output_dir / "data.toon").read_text(encoding="utf-8") == "a: 1\n"
