"""Tests for toon_tables.py.

The rules for turning the text in table cells into TOON data, shared by md_toon and
pdf_toon: which cells become numbers, how a column is typed as a whole, and how tables are
keyed and named.
"""

import pytest

from toon_tables import NOT_TYPED, FoundTable, cell_value, column_values, tables_to_data

# Cells


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("1", 1),
        ("-2", -2),
        ("0", 0),
        ("1.5", 1.5),
        ("-0.25", -0.25),
        ("1e-7", 1e-7),
        ("100000000000000000000", 10**20),
        ("true", True),
        ("false", False),
        ("null", None),
    ],
)
def test_a_cell_that_is_a_plain_value_is_read_as_one(text: str, value: object) -> None:
    result = cell_value(text)

    assert result == value
    assert type(result) is type(value)


@pytest.mark.parametrize(
    "text",
    [
        "007",  # a code or zip with leading zeros
        "1.50",  # same number as 1.5, but not the same text
        "1.0",
        "-0",
        "+1",
        "1,000",
        "True",
        "NULL",
        "NaN",
        "0x10",
        "12abc",
        "",
        " ",
        "Ana",
    ],
)
def test_a_cell_that_would_be_rewritten_stays_text(text: str) -> None:
    assert cell_value(text) is NOT_TYPED


# Columns


def test_a_column_of_numbers_is_typed() -> None:
    assert column_values(["1", "2.5", "-3"]) == [1, 2.5, -3]


def test_a_column_of_booleans_and_nulls_is_typed() -> None:
    assert column_values(["true", "false", "null"]) == [True, False, None]


def test_one_cell_that_is_not_a_value_keeps_the_whole_column_as_text() -> None:
    """Otherwise the column would hold numbers and strings together."""
    assert column_values(["1", "2", "n/a"]) == ["1", "2", "n/a"]


def test_leading_zeros_keep_the_whole_column_as_text() -> None:
    assert column_values(["007", "042", "100"]) == ["007", "042", "100"]


def test_a_blank_cell_is_null_when_the_rest_of_the_column_is_typed() -> None:
    assert column_values(["1", "", "3"]) == [1, None, 3]


def test_a_column_of_only_blanks_stays_text() -> None:
    assert column_values(["", ""]) == ["", ""]


def test_the_word_null_in_a_text_column_stays_text() -> None:
    assert column_values(["Ana", "null"]) == ["Ana", "null"]


# Tables


def table(*rows: list[str], title: str | None = None) -> FoundTable:
    return FoundTable(title, list(rows))


def test_a_lone_table_without_a_title_is_the_whole_document() -> None:
    data = tables_to_data([table(["id", "name"], ["1", "Ana"], ["2", "Bo"])])

    assert data == [{"id": 1, "name": "Ana"}, {"id": 2, "name": "Bo"}]


def test_a_lone_table_with_a_title_is_keyed_by_it() -> None:
    data = tables_to_data([table(["id"], ["1"], title="users")])

    assert data == {"users": [{"id": 1}]}


def test_tables_without_titles_are_numbered_by_position() -> None:
    data = tables_to_data([table(["a"], ["1"]), table(["b"], ["2"])])

    assert data == {"table_1": [{"a": 1}], "table_2": [{"b": 2}]}


def test_a_titled_table_next_to_an_untitled_one_keeps_its_position_number() -> None:
    data = tables_to_data([table(["a"], ["1"], title="first"), table(["b"], ["2"])])

    assert list(data) == ["first", "table_2"]


def test_tables_under_the_same_heading_get_numbered_keys() -> None:
    data = tables_to_data([
        table(["a"], ["1"], title="t"),
        table(["b"], ["2"], title="t"),
        table(["c"], ["3"], title="t"),
    ])

    assert list(data) == ["t", "t_2", "t_3"]


def test_a_table_with_only_a_header_is_an_empty_list() -> None:
    assert tables_to_data([table(["a", "b"])]) == []


def test_a_blank_column_name_is_numbered_by_position() -> None:
    assert tables_to_data([table(["", "b"], ["1", "2"])]) == [{"column_1": 1, "b": 2}]


def test_repeated_column_names_get_numbered() -> None:
    assert tables_to_data([table(["a", "a"], ["1", "2"])]) == [{"a": 1, "a_2": 2}]


def test_columns_are_typed_one_at_a_time() -> None:
    data = tables_to_data([table(["n", "code"], ["1", "007"], ["2", "042"])])

    assert data == [{"n": 1, "code": "007"}, {"n": 2, "code": "042"}]


def test_a_stray_short_or_long_row_does_not_break_the_table() -> None:
    data = tables_to_data([table(["a", "b"], ["x"], ["y", "z", "extra"])])

    assert data == [{"a": "x", "b": ""}, {"a": "y", "b": "z"}]


def test_no_tables_is_an_error() -> None:
    with pytest.raises(ValueError, match="no tables found"):
        tables_to_data([])
