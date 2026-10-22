"""Tests for toon_layout.py.

The rules for what becomes a table, a heading or a bullet. toon_md and toon_pdf both draw
what comes out of here, so these are tested once, on the blocks, rather than in each.
"""

import pytest

from toon_layout import NO_VALUE, Bullet, Heading, Table, Text, is_table, layout

# Tables


def test_a_list_of_matching_objects_is_one_table() -> None:
    data = [{"id": 1, "name": "Ana"}, {"id": 2, "name": "Bo"}]

    assert layout(data) == [Table(["id", "name"], [[1, "Ana"], [2, "Bo"]])]


def test_a_table_under_a_key_gets_a_heading() -> None:
    blocks = layout({"users": [{"id": 1}]})

    assert blocks == [Heading(1, "users"), Table(["id"], [[1]])]


def test_matching_objects_with_keys_in_another_order_stay_in_one_table() -> None:
    """Columns follow the first object, and each later row is read by key."""
    data = [{"a": 1, "b": 2}, {"b": 4, "a": 3}]

    assert layout(data) == [Table(["a", "b"], [[1, 2], [3, 4]])]


@pytest.mark.parametrize(
    "data",
    [
        pytest.param([{"a": 1}, {"b": 2}], id="different-keys"),
        pytest.param([{"a": 1}, {"a": 1, "b": 2}], id="extra-key"),
        pytest.param([{"a": 1}, 2], id="not-all-objects"),
        pytest.param([{"a": [1, 2]}], id="a-list-in-a-cell"),
        pytest.param([{"a": {"b": 1}}], id="an-object-in-a-cell"),
        pytest.param([{}], id="no-columns"),
        pytest.param([], id="empty-list"),
    ],
)
def test_these_are_not_tables(data: object) -> None:
    assert not is_table(data)


def test_an_empty_list_or_object_in_a_cell_does_not_stop_a_table() -> None:
    assert is_table([{"a": [], "b": {}}])


# Objects


def test_plain_entries_come_before_nested_sections() -> None:
    """Written after a nested section, a plain entry would read as part of that section."""
    blocks = layout({"author": {"name": "Evan"}, "version": 2})

    assert blocks == [
        Bullet(0, "version", 2),
        Heading(1, "author"),
        Bullet(0, "name", "Evan"),
    ]


def test_headings_get_one_level_deeper_per_nesting() -> None:
    blocks = layout({"a": {"b": {"c": 1}}})

    assert [b for b in blocks if isinstance(b, Heading)] == [Heading(1, "a"), Heading(2, "b")]


def test_headings_stop_getting_deeper_at_level_six() -> None:
    data: dict = {"k": 1}
    for name in "ghijklm":
        data = {name: data}

    levels = [block.level for block in layout(data) if isinstance(block, Heading)]

    assert levels == [1, 2, 3, 4, 5, 6, 6]


def test_an_empty_object_or_list_is_a_plain_value() -> None:
    assert layout({"a": {}, "b": []}) == [Bullet(0, "a", {}), Bullet(0, "b", [])]


# Lists


def test_a_list_of_plain_values_is_bullets() -> None:
    assert layout({"tags": ["a", "b"]}) == [
        Heading(1, "tags"),
        Bullet(0, None, "a"),
        Bullet(0, None, "b"),
    ]


def test_objects_in_a_list_that_do_not_match_are_numbered_items() -> None:
    blocks = layout([{"a": 1}, {"b": 2}, "x"])

    assert blocks == [
        Bullet(0, None, "Item 1"),
        Bullet(1, "a", 1),
        Bullet(0, None, "Item 2"),
        Bullet(1, "b", 2),
        Bullet(0, None, "x"),
    ]


def test_a_nested_list_inside_an_item_is_indented_one_more() -> None:
    blocks = layout([{"a": 1}, {"c": [1, 2]}])

    assert blocks[-3:] == [Bullet(1, "c"), Bullet(2, None, 1), Bullet(2, None, 2)]
    assert blocks[-3].value is NO_VALUE


# Lone values


@pytest.mark.parametrize("value", [42, "hello", None, True, {}, []])
def test_a_lone_value_is_text(value: object) -> None:
    assert layout(value) == [Text(value)]
