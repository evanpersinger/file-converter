"""Tests for html_svg.py, which prints HTML to PDF with headless Chrome and turns each
PDF page into an SVG with pymupdf.

The cases that need Chrome are skipped on a machine without it. The empty-input,
missing-Chrome and failed-Chrome cases run anywhere.
"""

import re
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

import html_svg

Sandbox = Callable[[ModuleType], tuple[Path, Path]]

needs_chrome = pytest.mark.skipif(
    not Path(html_svg.CHROME_PATH).exists(), reason="Google Chrome is not installed"
)

COLORED_PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
h1 { color: #d11f2e }
.box { background: #1f8a3c; color: #fff; padding: 12px; width: 240px }
</style></head><body><h1>Hello</h1><div class="box">Green box</div></body></html>"""


def test_reports_when_input_is_empty(sandbox: Sandbox) -> None:
    sandbox(html_svg)
    assert html_svg.convert_html_to_svg() == "No HTML files found in input folder"


def test_reports_when_the_file_is_already_an_svg(sandbox: Sandbox) -> None:
    input_dir, _ = sandbox(html_svg)
    (input_dir / "logo.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>')

    assert html_svg.convert_html_to_svg() == "That file is already in svg format"


def test_reports_when_chrome_is_missing(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, _ = sandbox(html_svg)
    (input_dir / "page.html").write_text(COLORED_PAGE)
    monkeypatch.setattr(html_svg, "CHROME_PATH", "/nonexistent/chrome")

    assert html_svg.convert_html_to_svg().startswith("Google Chrome not found")


def test_a_failed_chrome_run_is_reported_rather_than_raised(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`false` exits 1 and writes no PDF, which is what a Chrome failure looks like."""
    input_dir, _ = sandbox(html_svg)
    (input_dir / "page.html").write_text(COLORED_PAGE)
    monkeypatch.setattr(html_svg, "CHROME_PATH", "/usr/bin/false")

    summary = html_svg.convert_html_to_svg()

    assert summary.startswith("No files converted. 1 failed:")
    assert "page.html" in summary


@needs_chrome
@pytest.mark.parametrize("filename", ["page.html", "page.htm"])
def test_colors_survive_the_conversion(sandbox: Sandbox, filename: str) -> None:
    input_dir, output_dir = sandbox(html_svg)
    (input_dir / filename).write_text(COLORED_PAGE)

    summary = html_svg.convert_html_to_svg()

    assert "page.svg" in summary
    svg = (output_dir / "page.svg").read_text()
    assert "<svg" in svg
    fills = set(re.findall(r'fill="#([0-9a-fA-F]{6})"', svg))
    assert {"d11f2e", "1f8a3c"} <= {f.lower() for f in fills}


@needs_chrome
def test_a_long_page_splits_into_numbered_svgs(sandbox: Sandbox) -> None:
    input_dir, output_dir = sandbox(html_svg)
    paragraphs = "".join(f"<p>Paragraph {i}</p>" for i in range(150))
    (input_dir / "long.html").write_text(f"<!doctype html><body>{paragraphs}</body>")

    html_svg.convert_html_to_svg()

    names = sorted(p.name for p in output_dir.iterdir())
    assert names[:2] == ["long_page1.svg", "long_page2.svg"]
    assert "long.svg" not in names
