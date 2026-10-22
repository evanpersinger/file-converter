"""Convert the tables in Markdown files to TOON.

For each .md in input/, writes a .toon file to output/ holding its tables, each keyed by the
heading above it. Text that is not in a table is left out, and a file with no table fails.
"""

import re
from pathlib import Path

import mistune
import toon_format

from batch_convert import INPUT_DIR, OUTPUT_DIR, convert_files
from toon_tables import FoundTable, tables_to_data

_PARSER = mistune.create_markdown(renderer=None, plugins=['table'])

_LINE_BREAK = re.compile(r'<br\s*/?>', re.IGNORECASE)

# The start of a table the parser turned down: a header line, then a line of dashes. The
# parser only reads a table whose every row has as many cells as its header.
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
    """The tables in a document, each with the nearest heading above it. Only top-level
    ones: the parser does not find a table inside a quote or a list.

    Raises:
        ValueError: If something that looks like a table was not read as one, so it is
            reported rather than silently left out.
    """
    found = []
    title = None
    for token in tokens:
        kind = token['type']
        if kind == 'heading':
            title = _inline_text(token['children']).strip() or None
        elif kind == 'table':
            found.append(FoundTable(title, _rows(token)))
        elif kind == 'paragraph' and _REJECTED_TABLE.match(_inline_text(token['children'])):
            raise ValueError(
                "found what looks like a table but could not read it "
                "(every row needs the same number of cells as the header)"
            )
    return found


# convert a markdown file to toon text
# handles conversion logic
def markdown_to_toon(md_file):
    """Read a Markdown file and return its tables as TOON text"""
    # utf-8-sig so a file saved with a byte order mark still parses
    with open(md_file, 'r', encoding='utf-8-sig') as f:
        tokens = _PARSER(f.read())
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
