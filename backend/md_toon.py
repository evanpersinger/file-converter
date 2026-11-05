"""Convert the tables in Markdown files to TOON.

For each .md in input/, writes a .toon file to output/ holding its tables, each keyed by the
heading above it. Text that is not in a table is left out, and a file with no table fails.
"""

import re
from pathlib import Path

import mistune
import toon_format
from mistune.plugins.table import (
    CELL_SPLIT, NP_TABLE_PATTERN, TABLE_CELL, TABLE_PATTERN, _process_thead, table_in_list,
    table_in_quote,
)

from batch_convert import INPUT_DIR, OUTPUT_DIR, convert_files, read_text
from toon_tables import FoundTable, tables_to_data


def _gfm_rows(lines: list[str], aligns: list) -> list[dict]:
    """Table body lines as row tokens, each fitted to the header's width the way GitHub
    does it: a short row gets empty cells, and cells past the header's width are dropped."""
    rows = []
    for line in lines:
        cells = CELL_SPLIT.split(line)[:len(aligns)]
        cells += [''] * (len(aligns) - len(cells))
        rows.append({'type': 'table_row', 'children': [
            {'type': 'table_cell', 'text': text.strip(), 'attrs': {'align': align, 'head': False}}
            for text, align in zip(cells, aligns)
        ]})
    return rows


def _parse_table(block, m, state):
    """mistune's parse_table, except that rows whose cell count is off from the header's
    are fitted to it instead of the whole table being turned down."""
    thead, aligns = _process_thead(m.group('table_head'), m.group('table_align'))
    if not thead:
        return None
    lines = []
    for line in m.group('table_body').splitlines():
        cell = TABLE_CELL.match(line)
        if not cell:
            return None
        lines.append(cell.group(1))
    body = {'type': 'table_body', 'children': _gfm_rows(lines, aligns)}
    state.append_token({'type': 'table', 'children': [thead, body]})
    return m.end()


def _parse_nptable(block, m, state):
    """Like _parse_table, for a table written without the outer pipes."""
    thead, aligns = _process_thead(m.group('nptable_head'), m.group('nptable_align'))
    if not thead:
        return None
    body = {'type': 'table_body', 'children': _gfm_rows(m.group('nptable_body').splitlines(), aligns)}
    state.append_token({'type': 'table', 'children': [thead, body]})
    return m.end()


def _gfm_table(md: mistune.Markdown) -> None:
    """mistune's table plugin with GitHub's handling of short and long rows."""
    md.block.register('table', TABLE_PATTERN, _parse_table, before='paragraph')
    md.block.register('nptable', NP_TABLE_PATTERN, _parse_nptable, before='paragraph')


# table_in_quote and table_in_list also read a table inside a > quote or a list item
_PARSER = mistune.create_markdown(
    renderer=None, plugins=[_gfm_table, table_in_quote, table_in_list]
)

# Block tokens whose children can hold a table
_CONTAINERS = ('block_quote', 'list', 'list_item')

_LINE_BREAK = re.compile(r'<br\s*/?>', re.IGNORECASE)

# The start of a table the parser turned down: a header line, then a line of dashes. Now
# that rows are fitted to the header, that happens when the header and the line of dashes
# have a different number of cells.
_REJECTED_TABLE = re.compile(r'[^\n]*\|[^\n]*\n\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*(\n|$)')


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
    tokens = _PARSER(read_text(md_file, translate_newlines=True))
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
