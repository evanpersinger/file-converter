"""Convert the tables in Markdown files to TOON.

For each .md in input/, writes a .toon file to output/ holding its tables, each keyed by the
heading above it. Text that is not in a table is left out, and a file with no table fails.
"""

import re
from pathlib import Path

import mistune
import toon_format
from mistune.plugins.table import table_in_list, table_in_quote

from batch_convert import INPUT_DIR, OUTPUT_DIR, convert_files, read_text
from toon_tables import FoundTable, tables_to_data

# table_in_quote and table_in_list also read a table inside a > quote or a list item
_PARSER = mistune.create_markdown(
    renderer=None, plugins=['table', table_in_quote, table_in_list]
)

# Block tokens whose children can hold a table
_CONTAINERS = ('block_quote', 'list', 'list_item')

_LINE_BREAK = re.compile(r'<br\s*/?>', re.IGNORECASE)

# A table's line of dashes, with or without the outer pipes: `| - | :-: |` or `- | -`
_DASHES = r'\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*'

# The start of a table the parser turned down: a header line, then a line of dashes. Rows
# are fitted to the header before parsing, so that happens when the header and the line of
# dashes have a different number of cells.
_REJECTED_TABLE = re.compile(rf'[^\n]*\|[^\n]*\n\s*{_DASHES}(\n|$)')

# The quote markers and indentation a line starts with, then the rest of the line
_LINE_START = re.compile(r'([ \t]*(?:>[ \t]*)*)(.*)')


def _split_cells(row: str) -> list[str]:
    """The cells of a table row, split on the pipes that are not escaped with a backslash.
    A pipe at either end of the row is its edge, not a separator."""
    row = row.strip().removeprefix('|')
    cells, start, backslashes = [], 0, 0
    for index, char in enumerate(row):
        if char == '|' and backslashes % 2 == 0:
            cells.append(row[start:index])
            start = index + 1
        backslashes = backslashes + 1 if char == '\\' else 0
    cells.append(row[start:])
    if len(cells) > 1 and not cells[-1]:
        cells.pop()
    return cells


def _table_row(prefix: str, cells: list[str]) -> str:
    return prefix + '| ' + ' | '.join(cell.strip() for cell in cells) + ' |'


def _pad_ragged_tables(text: str) -> str:
    """The Markdown with each table whose rows are not as wide as its header fitted to it
    the way GitHub does: a short row gets empty cells, and cells past the header's width are
    dropped. The parser turns such a table down whole. A table inside a quote or a list item
    keeps its quote markers and indentation, and a table that is already even is left alone."""
    lines = text.split('\n')
    index = 0
    while index < len(lines) - 1:
        prefix, header = _LINE_START.fullmatch(lines[index]).groups()
        dash_prefix, dashes = _LINE_START.fullmatch(lines[index + 1]).groups()
        header_cells = _split_cells(header)
        if (prefix != dash_prefix or '|' not in header or not re.fullmatch(_DASHES, dashes)
                or len(header_cells) != len(_split_cells(dashes))):
            index += 1
            continue

        end = index + 2
        while end < len(lines):
            row_prefix, row = _LINE_START.fullmatch(lines[end]).groups()
            if row_prefix != prefix or '|' not in row:
                break
            end += 1

        width = len(header_cells)
        rows = [_split_cells(_LINE_START.fullmatch(line).group(2)) for line in lines[index + 2:end]]
        if any(len(cells) != width for cells in rows):
            fitted = [(cells + [''] * width)[:width] for cells in rows]
            lines[index:end] = [
                _table_row(prefix, cells) for cells in (header_cells, _split_cells(dashes), *fitted)
            ]
        index = end
    return '\n'.join(lines)


def _inline_text(tokens: list[dict]) -> str:
    """The text of inline Markdown, without its formatting. A <br> is a new line, and any
    other HTML tag is dropped."""
    parts = []
    for token in tokens:
        kind = token['type']
        if kind == 'inline_html':
            if _LINE_BREAK.fullmatch(token['raw']):
                parts.append('\n')
        elif kind in ('linebreak', 'softbreak'):
            parts.append('\n')
        elif 'children' in token:
            parts.append(_inline_text(token['children']))
        else:
            parts.append(token.get('raw', ''))
    return ''.join(parts)


def _rows(table: dict) -> list[list[str]]:
    """A table token as rows of cell text, header row first."""
    head, body = table['children']
    rows = [[_inline_text(cell['children']).strip() for cell in head['children']]]
    for row in body['children']:
        rows.append([_inline_text(cell['children']).strip() for cell in row['children']])
    return rows


def _find_tables(tokens: list[dict]) -> list[FoundTable]:
    """The tables in a document, each with the nearest heading above it, including tables
    inside a quote or a list item.

    Raises:
        ValueError: If something that looks like a table was not read as one, so it is
            reported rather than silently left out.
    """
    found: list[FoundTable] = []
    title = None

    def walk(tokens: list[dict]) -> None:
        nonlocal title
        for token in tokens:
            kind = token['type']
            if kind == 'heading':
                title = _inline_text(token['children']).strip() or None
            elif kind == 'table':
                found.append(FoundTable(title, _rows(token)))
            elif kind in _CONTAINERS:
                walk(token['children'])
            elif (kind in ('paragraph', 'block_text')
                  and _REJECTED_TABLE.match(_inline_text(token['children']))):
                raise ValueError(
                    "found what looks like a table but could not read it "
                    "(the header and the line of dashes under it need the same number of cells)"
                )

    walk(tokens)
    return found


# convert a markdown file to toon text
# handles conversion logic
def markdown_to_toon(md_file):
    """Read a Markdown file and return its tables as TOON text"""
    # read_text drops a byte order mark and takes a file that is not UTF-8
    tokens = _PARSER(_pad_ragged_tables(read_text(md_file, translate_newlines=True)))
    return toon_format.dumps(tables_to_data(_find_tables(tokens))) + '\n'


def _write_toon(source: Path, dest: Path) -> None:
    dest.write_text(markdown_to_toon(source), encoding='utf-8')


# convert all markdown files to toon files
# handles file system operations
def convert_markdown_to_toon(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert the tables in all Markdown files in the input folder to TOON files in the
    output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_files(
        input_dir, output_dir, ('.md',), ('.toon',), _write_toon,
        source_label="Markdown", target_label="TOON",
    )


if __name__ == "__main__":
    result = convert_markdown_to_toon()
    if not result.startswith("Converted"):
        print(result)
