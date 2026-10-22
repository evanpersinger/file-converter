"""Turns tables found in a document into TOON data, for md_toon and pdf_toon.

Cells arrive as text. A column becomes numbers, true/false or null only when every cell in
it reads that way without being rewritten, so 007 and 1.50 stay text.
"""

import json
import re
from dataclasses import dataclass

import toon_format

# The shape of a JSON number, which is what TOON writes numbers as
_NUMBER = re.compile(r'-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?')

# Marks a cell that is not a number, true, false or null
NOT_TYPED = object()


@dataclass(frozen=True)
class FoundTable:
    """A table in a document: the heading above it if there is one, and its rows with the
    header row first."""

    title: str | None
    rows: list[list[str]]


def cell_value(text: str):
    """What a cell holds if reading it as a value loses nothing, else NOT_TYPED.

    TOON writes the value back out, so a number is only a number if TOON would write the
    same text: 1.5 and 42 are, 1.50 and 1.0 and -0 and 007 are not.
    """
    if text in ('true', 'false', 'null'):
        return json.loads(text)
    if _NUMBER.fullmatch(text):
        value = json.loads(text)
        if toon_format.dumps(value) == text:
            return value
    return NOT_TYPED


def column_values(texts: list[str]) -> list:
    """A column of cells as values: all typed, or all left as text.

    Blank cells count as null when the rest of the column is typed. A column that is all
    blank, or has any cell that is not a plain value, stays text, so no column ends up
    holding a mix of numbers and strings.
    """
    typed = [None if text == '' else cell_value(text) for text in texts]
    if all(text == '' for text in texts) or any(value is NOT_TYPED for value in typed):
        return texts
    return typed


def _unique(name: str, taken: set[str]) -> str:
    """name, or name_2, name_3 ... if it is already taken."""
    candidate, number = name, 2
    while candidate in taken:
        candidate = f'{name}_{number}'
        number += 1
    return candidate


def _array(rows: list[list[str]]) -> list[dict]:
    """One table as a list of objects, the header row giving the keys."""
    keys: list[str] = []
    for column, name in enumerate(rows[0], start=1):
        keys.append(_unique(name or f'column_{column}', set(keys)))

    # Every row should be as wide as the header. A stray one is filled out with blanks or cut
    # off anyway, so it cannot break the table.
    body = [(row + [''] * len(keys))[:len(keys)] for row in rows[1:]]
    columns = [column_values([row[index] for row in body]) for index in range(len(keys))]
    return [dict(zip(keys, values)) for values in zip(*columns)] if body else []


def tables_to_data(tables: list[FoundTable]):
    """The TOON data for the tables in a document.

    A lone table with no title is the whole document, a list of objects. Otherwise each
    table is a key holding its list of objects: the heading above it, or table_1, table_2.

    Raises:
        ValueError: If there are no tables.
    """
    if not tables:
        raise ValueError('no tables found (only tables are converted)')
    if len(tables) == 1 and tables[0].title is None:
        return _array(tables[0].rows)

    data: dict[str, list[dict]] = {}
    for number, table in enumerate(tables, start=1):
        key = _unique(table.title or f'table_{number}', set(data))
        data[key] = _array(table.rows)
    return data
