"""Convert TOON files to PDF.

For each .toon in input/, draws a PDF with reportlab in output/: arrays of matching
objects become tables, other objects and lists become headings and bullets. Values are
drawn as text, never read as markup. Only Latin text can be drawn.
"""

from pathlib import Path
from xml.sax.saxutils import escape

import toon_format
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    CondPageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from batch_convert import INPUT_DIR, OUTPUT_DIR, convert_files
from toon_layout import NO_VALUE, Block, Bullet, Heading, Text, json_text, layout
from toon_layout import Table as TableBlock

BULLET_INDENT = 14
# A heading starts a new page when less than this much room is left, so it is never
# stranded at the bottom with its content on the next page.
HEADING_MIN_SPACE = 90
# A table column is never given less than this many characters of width, or more than the
# longest cell up to MAX_COLUMN_CHARS, so short columns (ids) stay narrow and a long one
# (a description) gets the room.
MIN_COLUMN_CHARS = 6
MAX_COLUMN_CHARS = 40

_STYLES = getSampleStyleSheet()
_BODY = ParagraphStyle('ToonBody', parent=_STYLES['Normal'], fontSize=10, leading=13)
_CELL = ParagraphStyle('ToonCell', parent=_BODY, fontSize=9, leading=11)
_HEADER_CELL = ParagraphStyle('ToonHeaderCell', parent=_CELL, fontName='Helvetica-Bold')


def _markup(value) -> str:
    """A value as Paragraph markup. Strings are escaped so they are drawn as written, the
    rest are spelled the way JSON spells them (null, true, 1.5, {}).

    Raises:
        ValueError: If the font cannot draw a character in the string.
    """
    if not isinstance(value, str):
        return json_text(value)
    try:
        value.encode('cp1252')
    except UnicodeEncodeError as e:
        raise ValueError(
            f"the PDF font cannot draw {e.object[e.start:e.end]!r} (only Latin text is supported)"
        ) from None
    return escape(value).replace('\r\n', '<br/>').replace('\r', '<br/>').replace('\n', '<br/>')


def _bullet(bullet: Bullet) -> Paragraph:
    parts = []
    if bullet.key is not None:
        parts.append(f'<b>{_markup(bullet.key)}</b>:')
    if bullet.value is not NO_VALUE:
        parts.append(_markup(bullet.value))
    style = ParagraphStyle(
        'ToonBullet',
        parent=_BODY,
        leftIndent=BULLET_INDENT * (bullet.indent + 1),
        bulletIndent=BULLET_INDENT * bullet.indent,
    )
    return Paragraph(' '.join(parts), style, bulletText='•')


def _table(block: TableBlock, width: float) -> Table:
    rows = [[Paragraph(_markup(key), _HEADER_CELL) for key in block.keys]]
    for row in block.rows:
        rows.append([Paragraph(_markup(value), _CELL) for value in row])

    # Wider columns for longer content, within limits, scaled to fill the page width
    weights = [
        min(
            MAX_COLUMN_CHARS,
            max(MIN_COLUMN_CHARS, len(key), *(len(str(row[column])) for row in block.rows)),
        )
        for column, key in enumerate(block.keys)
    ]
    widths = [width * weight / sum(weights) for weight in weights]

    table = Table(rows, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    return table


def _story(blocks: list[Block], width: float) -> list:
    """The blocks as reportlab flowables."""
    story = []
    for block in blocks:
        if isinstance(block, Heading):
            story.append(CondPageBreak(HEADING_MIN_SPACE))
            story.append(Paragraph(_markup(block.text), _STYLES[f'Heading{block.level}']))
        elif isinstance(block, TableBlock):
            story.extend([_table(block, width), Spacer(1, 8)])
        elif isinstance(block, Bullet):
            story.append(_bullet(block))
        elif isinstance(block, Text):
            story.append(Paragraph(_markup(block.value), _BODY))
    return story


# convert a toon file to a pdf
# handles conversion logic
def toon_to_pdf(toon_file: Path, pdf_file: Path) -> None:
    """Read a TOON file and write it to pdf_file as a PDF"""
    # utf-8-sig so a file saved with a byte order mark still parses
    with open(toon_file, 'r', encoding='utf-8-sig') as f:
        data = toon_format.loads(f.read())
    doc = SimpleDocTemplate(str(pdf_file), pagesize=letter, title=Path(toon_file).stem)
    doc.build(_story(layout(data), doc.width))


# convert all toon files to pdf files
# handles file system operations
def convert_toon_to_pdf(
    input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUTPUT_DIR
) -> str:
    """Convert all TOON files in the input folder to PDF files in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """
    return convert_files(input_dir, output_dir, ('.toon',), ('.pdf',), toon_to_pdf)


if __name__ == "__main__":
    result = convert_toon_to_pdf()
    if not result.startswith("Converted"):
        print(result)
