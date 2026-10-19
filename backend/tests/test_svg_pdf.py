"""Tests for svg_pdf.py, which prints each SVG to a one-page PDF with headless Chrome.

Chrome prints a bare SVG onto a Letter page and clips what does not fit, so the page size
and the large-SVG cases matter most. The cases that need Chrome are skipped on a machine
without it. The size parsing and the empty-input, missing-Chrome and failed-Chrome cases
run anywhere.
"""

from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import fitz
import pytest

import html_svg
import svg_pdf

Sandbox = Callable[[ModuleType], tuple[Path, Path]]

needs_chrome = pytest.mark.skipif(
    not Path(html_svg.CHROME_PATH).exists(), reason="Google Chrome is not installed"
)

SVG_NS = 'xmlns="http://www.w3.org/2000/svg"'
SHAPES = (
    '<rect x="50" y="50" width="100" height="100" fill="#d11f2e"/>'
    '<circle cx="450" cy="150" r="80" fill="#1f8a3c"/>'
)
STYLED = (
    "<style>.box { fill: #1f8a3c }</style>"
    '<rect class="box" x="50" y="50" width="200" height="100"/>'
)


def svg(width: str, height: str, body: str = SHAPES) -> str:
    return f'<svg {SVG_NS} width="{width}" height="{height}">{body}</svg>'


def pixel(pdf: Path, x: int, y: int) -> tuple[int, ...]:
    """The RGBA value at (x, y) when the first page is drawn at 96 dpi, one pixel per CSS px."""
    with fitz.open(pdf) as document:
        return document[0].get_pixmap(dpi=96, alpha=True).pixel(x, y)


@pytest.mark.parametrize(
    "attributes, expected",
    [
        ('width="600" height="300"', (600, 300)),
        ('width="72pt" height="36pt"', (96, 48)),
        ('width="1in" height="2in"', (96, 192)),
        ('width="10mm" height="20mm"', (37.795, 75.591)),
        ('width="100%" height="100%" viewBox="0 0 400 200"', (400, 200)),
        ('viewBox="0,0,50,25"', (50, 25)),
    ],
)
def test_the_size_is_read_in_css_pixels(
    tmp_path: Path, attributes: str, expected: tuple[float, float]
) -> None:
    svg_file = tmp_path / "shape.svg"
    svg_file.write_text(f"<svg {SVG_NS} {attributes}></svg>")

    assert svg_pdf.svg_size(str(svg_file)) == pytest.approx(expected, abs=0.01)


def test_reports_when_input_is_empty(sandbox: Sandbox) -> None:
    sandbox(svg_pdf)
    assert svg_pdf.convert_svg_to_pdf() == "No SVG files found in input folder"


def test_reports_when_the_file_is_already_a_pdf(sandbox: Sandbox) -> None:
    input_dir, _ = sandbox(svg_pdf)
    (input_dir / "doc.pdf").write_bytes(b"%PDF-1.4")

    assert svg_pdf.convert_svg_to_pdf() == "That file is already in pdf format"


def test_reports_when_chrome_is_missing(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, _ = sandbox(svg_pdf)
    (input_dir / "shape.svg").write_text(svg("600", "300"))
    monkeypatch.setattr(html_svg, "CHROME_PATH", "/nonexistent/chrome")

    assert svg_pdf.convert_svg_to_pdf().startswith("Google Chrome not found")


def test_a_failed_chrome_run_is_reported_rather_than_raised(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`false` exits 1 and writes no PDF, which is what a Chrome failure looks like."""
    input_dir, _ = sandbox(svg_pdf)
    (input_dir / "shape.svg").write_text(svg("600", "300"))
    monkeypatch.setattr(html_svg, "CHROME_PATH", "/usr/bin/false")

    summary = svg_pdf.convert_svg_to_pdf()

    assert summary.startswith("No files converted. 1 failed:")
    assert "shape.svg" in summary


def test_an_svg_with_no_size_is_reported_rather_than_raised(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, _ = sandbox(svg_pdf)
    (input_dir / "sizeless.svg").write_text(f"<svg {SVG_NS}>{SHAPES}</svg>")
    monkeypatch.setattr(html_svg, "CHROME_PATH", "/usr/bin/false")

    summary = svg_pdf.convert_svg_to_pdf()

    assert "sizeless.svg" in summary
    assert "size is unknown" in summary


@needs_chrome
@pytest.mark.parametrize("filename", ["shape.svg", "shape.SVG"])
def test_the_page_is_the_size_of_the_svg(sandbox: Sandbox, filename: str) -> None:
    input_dir, output_dir = sandbox(svg_pdf)
    (input_dir / filename).write_text(svg("600", "300"))

    summary = svg_pdf.convert_svg_to_pdf()

    assert "shape.pdf" in summary
    with fitz.open(output_dir / "shape.pdf") as document:
        assert document.page_count == 1
        # 600 x 300 CSS pixels is 450 x 225 points
        assert tuple(document[0].rect)[2:] == pytest.approx((450, 225), abs=1)
    assert pixel(output_dir / "shape.pdf", 100, 100)[:3] == pytest.approx((209, 31, 46), abs=3)
    assert pixel(output_dir / "shape.pdf", 2, 2)[3] == 0


@needs_chrome
def test_a_large_svg_is_not_clipped(sandbox: Sandbox) -> None:
    input_dir, output_dir = sandbox(svg_pdf)
    body = '<circle cx="1400" cy="1000" r="150" fill="#1f8a3c"/>'
    (input_dir / "big.svg").write_text(svg("1600", "1200", body))

    svg_pdf.convert_svg_to_pdf()

    with fitz.open(output_dir / "big.pdf") as document:
        assert document.page_count == 1
    assert pixel(output_dir / "big.pdf", 1400, 1000)[:3] == pytest.approx((31, 138, 60), abs=3)


@needs_chrome
def test_an_odd_size_still_gives_one_page(sandbox: Sandbox) -> None:
    input_dir, output_dir = sandbox(svg_pdf)
    (input_dir / "odd.svg").write_text(svg("333", "777"))

    svg_pdf.convert_svg_to_pdf()

    with fitz.open(output_dir / "odd.pdf") as document:
        assert document.page_count == 1


@needs_chrome
def test_css_in_the_svg_is_applied(sandbox: Sandbox) -> None:
    """A renderer that ignores <style> would draw this box black."""
    input_dir, output_dir = sandbox(svg_pdf)
    (input_dir / "styled.svg").write_text(svg("300", "200", STYLED))

    svg_pdf.convert_svg_to_pdf()

    assert pixel(output_dir / "styled.pdf", 150, 100)[:3] == pytest.approx((31, 138, 60), abs=3)


@needs_chrome
def test_one_bad_file_does_not_stop_the_good_ones(sandbox: Sandbox) -> None:
    input_dir, output_dir = sandbox(svg_pdf)
    (input_dir / "good.svg").write_text(svg("600", "300"))
    (input_dir / "broken.svg").write_text("this is not an svg")

    summary = svg_pdf.convert_svg_to_pdf()

    assert "good.pdf" in summary
    assert "1 failed" in summary
    assert "broken.svg" in summary
    assert (output_dir / "good.pdf").exists()
