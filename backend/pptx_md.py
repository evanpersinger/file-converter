"""Convert PowerPoint (.pptx) files to Markdown.

For each .pptx in input/, walks every slide with python-pptx, adds a `## Slide N`
heading, promotes large-font text to subheadings, and writes the text to output/.
"""

import os
import glob
from pptx import Presentation
from pptx.shapes.group import GroupShape

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Folders
input_folder = os.path.join(script_dir, 'input')
output_folder = os.path.join(script_dir, 'output')


def _cell_text(cell):
    """Cell text on one line, with pipes escaped so they stay inside the cell."""
    if cell.is_spanned:
        return ""
    return " ".join(cell.text.split()).replace("|", "\\|")


def _table_to_markdown(table):
    """Render a table as Markdown, treating the first row as the header.

    Markdown has no column span, so a cell covered by a merge comes out empty and
    the text stays in the cell the merge started from.
    """
    header, *body = [[_cell_text(cell) for cell in row.cells] for row in table.rows]
    lines = ['| ' + ' | '.join(header) + ' |',
             '| ' + ' | '.join(['---'] * len(header)) + ' |']
    lines += ['| ' + ' | '.join(row) + ' |' for row in body]
    return '\n'.join(lines)


def _append_shape_text(shape, markdown_content):
    """Append one shape's text to markdown_content, recursing into groups."""
    if isinstance(shape, GroupShape):
        for child in shape.shapes:
            _append_shape_text(child, markdown_content)
        return

    if shape.has_table:
        # Blank lines on both sides, or a neighbouring line gets read as part of the table
        markdown_content.append(f"\n{_table_to_markdown(shape.table)}\n\n")
        return

    if hasattr(shape, "text") and shape.text.strip():
        text = shape.text.strip()

        # Check if this is likely a title
        if hasattr(shape, "text_frame") and shape.text_frame.paragraphs:
            first_para = shape.text_frame.paragraphs[0]
            if first_para.runs and first_para.runs[0].font.size:
                if first_para.runs[0].font.size > 200000:
                    markdown_content.append(f"### {text}\n")
                    return

        markdown_content.append(f"{text}\n")


def extract_text_from_pptx(pptx_file):
    """Extract text from PowerPoint file and format as markdown"""
    prs = Presentation(pptx_file)
    markdown_content = []

    for slide_num, slide in enumerate(prs.slides, start=1):
        markdown_content.append(f"## Slide {slide_num}\n")

        for shape in slide.shapes:
            _append_shape_text(shape, markdown_content)

        markdown_content.append("\n---\n\n")

    return ''.join(markdown_content)


def convert_pptx_to_markdown() -> str:
    """Convert all PPTX files in the input folder to Markdown files in the output folder.

    Returns:
        A summary of what was converted, suitable for showing to a caller.
    """

    # Create output folder if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Find all PPTX files
    pptx_files = glob.glob(os.path.join(input_folder, '*.pptx'))

    if not pptx_files:
        # If there are only markdown files present, notify the user
        md_present = glob.glob(os.path.join(input_folder, '*.md'))
        if md_present:
            return "That file is already in markdown format"
        return "No PPTX files found in input folder"

    converted = []
    errors = []

    for pptx_file in pptx_files:
        try:
            # Get filename without extension
            filename = os.path.splitext(os.path.basename(pptx_file))[0]
            md_file = os.path.join(output_folder, f"{filename}.md")

            print(f"Converting {os.path.basename(pptx_file)} to md")

            # Extract text and format as markdown
            markdown_content = extract_text_from_pptx(pptx_file)

            # Write to markdown file
            existed_before = os.path.exists(md_file)
            with open(md_file, 'w', encoding='utf-8') as f:
                f.write(markdown_content)

            print(f"Converted {os.path.basename(pptx_file)} to {filename}.md")
            if existed_before:
                print(f"Overwrote existing file: {filename}.md")
            converted.append(f"{filename}.md")

        except Exception as e:
            print(f"Error converting {pptx_file}: {str(e)}")
            errors.append(f"{os.path.basename(pptx_file)}: {e}")

    if not converted:
        return f"No files converted. {len(errors)} failed: {'; '.join(errors)}"

    summary = f"Converted {len(converted)} file(s) to output/: {', '.join(converted)}"
    if errors:
        summary += f". {len(errors)} failed: {'; '.join(errors)}"
    return summary


if __name__ == "__main__":
    result = convert_pptx_to_markdown()
    if not result.startswith("Converted"):
        print(result)
