"""Lays TOON data out as headings, tables and bullets, for toon_md and toon_pdf to draw.

The rules for what becomes a table, a heading or a bullet live here, so both outputs agree.
"""

import json
from dataclasses import dataclass

MAX_HEADING_LEVEL = 6

# Marks a bullet that has a key but no value, as opposed to a value of null
NO_VALUE = object()


@dataclass(frozen=True)
class Heading:
    level: int
    text: str


@dataclass(frozen=True)
class Table:
    keys: list[str]
    rows: list[list]


@dataclass(frozen=True)
class Bullet:
    """One bullet: `key: value`, `key:` when there is no value, or just the value.
    `indent` is how many bullets deep it is nested."""

    indent: int
    key: str | None = None
    value: object = NO_VALUE


@dataclass(frozen=True)
class Text:
    """A lone value with nothing around it, like a file that holds only a number."""

    value: object


Block = Heading | Table | Bullet | Text


def is_leaf(value) -> bool:
    """A plain value, or an empty object or list, which is written as {} or []."""
    return not isinstance(value, (dict, list)) or not value


def is_table(items) -> bool:
    """True for a list of objects that share the same keys and hold only plain values,
    which is the shape of both a TOON table and a Markdown table."""
    if not isinstance(items, list) or not items:
        return False
    if not all(isinstance(item, dict) for item in items):
        return False
    keys = set(items[0])
    return bool(keys) and all(
        set(item) == keys and all(is_leaf(value) for value in item.values()) for item in items
    )


def json_text(value) -> str:
    """A plain value spelled the way JSON spells it (null, true, 1.5, {})."""
    return json.dumps(value, ensure_ascii=False)


def layout(data) -> list[Block]:
    """The blocks for a TOON document, in reading order.

    An object's plain entries come first, then a heading for each key holding a nested
    object or list, one level deeper each time (down to MAX_HEADING_LEVEL). Written in that
    order, a plain entry is never read as belonging to the section above it. A list of
    matching objects is a table, and any other list is nested bullets, with `Item N` over
    each object or list inside it.
    """
    return _blocks(data, 1)


def _blocks(value, level: int) -> list[Block]:
    if isinstance(value, dict) and value:
        blocks: list[Block] = [
            Bullet(0, key, item) for key, item in value.items() if is_leaf(item)
        ]
        for key, item in value.items():
            if not is_leaf(item):
                blocks.append(Heading(min(level, MAX_HEADING_LEVEL), key))
                blocks.extend(_blocks(item, level + 1))
        return blocks
    if is_table(value):
        keys = list(value[0])
        return [Table(keys, [[item[key] for key in keys] for item in value])]
    if is_leaf(value):
        return [Text(value)]
    return _bullets(value, 0)


def _bullets(value, indent: int) -> list[Block]:
    """Any object or list as a nested bullet list, one bullet per entry."""
    bullets: list[Block] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if is_leaf(item):
                bullets.append(Bullet(indent, key, item))
            else:
                bullets.append(Bullet(indent, key))
                bullets.extend(_bullets(item, indent + 1))
    else:
        for number, item in enumerate(value, start=1):
            if is_leaf(item):
                bullets.append(Bullet(indent, None, item))
            else:
                bullets.append(Bullet(indent, None, f'Item {number}'))
                bullets.extend(_bullets(item, indent + 1))
    return bullets
