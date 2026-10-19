"""Tests for svg_png.py, which renders each SVG with headless Chrome and saves it as a PNG.

The pixel size, the transparent background and the large-SVG cases matter most: the PNG
should be one pixel per CSS pixel of the SVG, not a Letter page with the SVG clipped inside
it. The cases that need Chrome are skipped on a machine without it. The empty-input,
missing-Chrome and failed-Chrome cases run anywhere.
"""

from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest
from PIL import Image

import html_svg
import svg_png

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


def test_reports_when_input_is_empty(sandbox: Sandbox) -> None:
    sandbox(svg_png)
    assert svg_png.convert_svg_to_png() == "No SVG files found in input folder"


def test_reports_when_the_file_is_already_a_png(sandbox: Sandbox) -> None:
    input_dir, _ = sandbox(svg_png)
    Image.new("RGB", (4, 4)).save(input_dir / "photo.png", "PNG")

    assert svg_png.convert_svg_to_png() == "That file is already in png format"


def test_reports_when_chrome_is_missing(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir, _ = sandbox(svg_png)
    (input_dir / "shape.svg").write_text(svg("600", "300"))
    monkeypatch.setattr(html_svg, "CHROME_PATH", "/nonexistent/chrome")

    assert svg_png.convert_svg_to_png().startswith("Google Chrome not found")


def test_a_failed_chrome_run_is_reported_rather_than_raised(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`false` exits 1 and writes no PDF, which is what a Chrome failure looks like."""
    input_dir, _ = sandbox(svg_png)
    (input_dir / "shape.svg").write_text(svg("600", "300"))
    monkeypatch.setattr(html_svg, "CHROME_PATH", "/usr/bin/false")

    summary = svg_png.convert_svg_to_png()

    assert summary.startswith("No files converted. 1 failed:")
    assert "shape.svg" in summary


@needs_chrome
@pytest.mark.parametrize("filename", ["shape.svg", "shape.SVG"])
def test_the_png_is_the_size_of_the_svg(sandbox: Sandbox, filename: str) -> None:
    input_dir, output_dir = sandbox(svg_png)
    (input_dir / filename).write_text(svg("600", "300"))

    summary = svg_png.convert_svg_to_png()

    assert "shape.png" in summary
    with Image.open(output_dir / "shape.png") as png:
        assert png.format == "PNG"
        assert png.size == (600, 300)
        rgba = png.convert("RGBA")
    assert rgba.getpixel((100, 100))[:3] == pytest.approx((209, 31, 46), abs=3)
    assert rgba.getpixel((2, 2))[3] == 0


@needs_chrome
def test_a_large_svg_is_not_clipped(sandbox: Sandbox) -> None:
    input_dir, output_dir = sandbox(svg_png)
    body = '<circle cx="1400" cy="1000" r="150" fill="#1f8a3c"/>'
    (input_dir / "big.svg").write_text(svg("1600", "1200", body))

    svg_png.convert_svg_to_png()

    with Image.open(output_dir / "big.png") as png:
        assert png.size == (1600, 1200)
        assert png.convert("RGB").getpixel((1400, 1000)) == pytest.approx((31, 138, 60), abs=3)


@needs_chrome
@pytest.mark.parametrize("width, height", [(24, 24), (100, 50), (333, 777)])
def test_an_odd_size_gives_exactly_that_many_pixels(
    sandbox: Sandbox, width: int, height: int
) -> None:
    """Chrome rounds some page sizes up a pixel (100x50 comes back 101x51 unfixed)."""
    input_dir, output_dir = sandbox(svg_png)
    (input_dir / "odd.svg").write_text(svg(str(width), str(height)))

    svg_png.convert_svg_to_png()

    with Image.open(output_dir / "odd.png") as png:
        assert png.size == (width, height)


@needs_chrome
def test_css_in_the_svg_is_applied(sandbox: Sandbox) -> None:
    """A renderer that ignores <style> would draw this box black."""
    input_dir, output_dir = sandbox(svg_png)
    (input_dir / "styled.svg").write_text(svg("300", "200", STYLED))

    svg_png.convert_svg_to_png()

    with Image.open(output_dir / "styled.png") as png:
        assert png.convert("RGB").getpixel((150, 100)) == pytest.approx((31, 138, 60), abs=3)


@needs_chrome
def test_one_bad_file_does_not_stop_the_good_ones(sandbox: Sandbox) -> None:
    input_dir, output_dir = sandbox(svg_png)
    (input_dir / "good.svg").write_text(svg("600", "300"))
    (input_dir / "broken.svg").write_text("this is not an svg")

    summary = svg_png.convert_svg_to_png()

    assert "good.png" in summary
    assert "1 failed" in summary
    assert "broken.svg" in summary
    assert (output_dir / "good.png").exists()
