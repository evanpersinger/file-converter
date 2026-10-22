"""Convert TOON files to Markdown.

For each .toon in input/, writes a .md file to output/: arrays of matching objects become
tables, other objects and lists become headings and bullets.
"""

import re
from pathlib import Path

import toon_format

from batch_convert import INPUT_DIR, OUTPUT_DIR, convert_files
from toon_layout import NO_VALUE, Block, Bullet, Heading, Table, json_text, layout


def _text(value) -> str:
    """A value as Markdown text. Strings are escaped so they show as written, the rest are
    spelled the way JSON spells them (null, true, 1.5, {})."""
    if isinstance(value, str):
        escaped = re.sub(r'([\\`*_\[\]<>|])', r'\\\1', value)
        return re.sub(r'\r\n|\r|\n', '<br>', escaped)
    return json_text(value)


def _table(table: Table) -> str:
    lines = [
        '| ' + ' | '.join(_text(key) for key in table.keys) + ' |',
        '| ' + ' | '.join('---' for _ in table.keys) + ' |',
    ]
    for row in table.rows:
        lines.append('| ' + ' | '.join(_text(value) for value in row) + ' |')
    return '\n'.join(lines)


def _bullet(bullet: Bullet) -> str:
    parts = []
    if bullet.key is not None:
        parts.append(f'**{_text(bullet.key)}**:')
    if bullet.value is not NO_VALUE:
        parts.append(_text(bullet.value))
    return '  ' * bullet.indent + '- ' + ' '.join(parts)


def _markdown(blocks: list[Block]) -> str:
    """The blocks as Markdown, separated by blank lines. A run of bullets is one list."""
    paragraphs = []
    bullets = []
    for block in blocks:
        if isinstance(block, Bullet):
            bullets.append(_bullet(block))
            continue
        if bullets:
            paragraphs.append('\n'.join(bullets))
            bullets = []
        if isinstance(block, Heading):
            paragraphs.append('#' * block.level + ' ' + _text(block.text))
        elif isinstance(block, Table):
            paragraphs.append(_table(block))
        else:
            paragraphs.append(_text(block.value))
    if bullets:
        paragraphs.append('\n'.join(bullets))
    return '\n\n'.join(paragraphs) + '\n'


# convert a toon file to markdown text
# handles conversion logic
def toon_to_markdown(toon_file):
    """Read a TOON file and return it as Markdown text"""
    # utf-8-sig so a file saved with a byte order mark still parses
    with open(toon_file, 'r', encoding='utf-8-sig') as f:
        data = toon_format.loads(f.read())
    return _markdown(layout(data))


def _write_markdown(source: Path, dest: Path) -> None:
    dest.write_text(toon_to_markdown(source), encoding='utf-8')


# convert all toon files to markdown files
# handles file system operations
def convert_toon_to_markdown(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all TOON files in the input folder to Markdown files in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_files(
        input_dir, output_dir, ('.toon',), ('.md',), _write_markdown, target_label="markdown"
    )


if __name__ == "__main__":
    result = convert_toon_to_markdown()
    if not result.startswith("Converted"):
        print(result)
