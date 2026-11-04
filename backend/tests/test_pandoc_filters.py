"""Tests for pandoc_filters.py, the Lua filter that keeps uploads from embedding local images."""

import shutil
import subprocess

import pytest

import md_pdf
import pandoc_filters

pytestmark = pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc not installed")


def through_filter(markdown: str, from_fmt: str = "markdown+raw_tex") -> str:
    """Run markdown through the filter and back to Markdown, so the result is easy to read."""
    with pandoc_filters.local_files_filter() as args:
        result = subprocess.run(
            ["pandoc", f"--from={from_fmt}", "--to=markdown", *args],
            input=markdown, capture_output=True, text=True, check=True,
        )
    return result.stdout


@pytest.mark.parametrize("src", ["/etc/secret.png", "../up/one.png", "photo.png", "file:///etc/x.png"])
def test_local_images_become_their_alt_text(src: str) -> None:
    out = through_filter(f"![the alt]({src})\n")

    assert src not in out
    assert "the alt" in out


@pytest.mark.parametrize("src", ["data:image/png;base64,iVBORw0KGgo=", "https://example.com/a.png", "HTTP://example.com/a.png"])
def test_data_and_web_images_are_kept(src: str) -> None:
    assert src in through_filter(f"![x]({src})\n")


def test_html_img_tags_pointing_at_local_files_are_dropped() -> None:
    out = through_filter('<p>Hi <img src="/etc/secret.png" alt="pic"></p>', from_fmt="html")

    assert "/etc/secret.png" not in out
    assert "Hi" in out


@pytest.mark.parametrize("tex, command", [
    (r"\includegraphics{/etc/secret.png}", r"\includegraphics"),
    (r'\XeTeXpicfile "/etc/secret.png"', r"\XeTeXpicfile"),
    (r"\csname includegraphics\endcsname{/etc/secret.png}", r"csname"),
])
def test_raw_latex_that_loads_files_is_dropped(tex: str, command: str) -> None:
    """pandoc may split a command from its argument; the argument left over is plain text."""
    out = through_filter(f"Before {tex} after\n")

    assert command not in out
    assert "Before" in out and "after" in out


def test_ordinary_raw_latex_and_math_are_kept() -> None:
    out = through_filter("A \\textbf{bold} word and $x^2$.\n")

    assert "\\textbf{bold}" in out
    assert "$x^2$" in out


def test_md_pdf_runs_the_filter_before_mermaid_filter(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Otherwise the diagram images mermaid-filter writes to disk would be dropped too."""
    commands = []

    def fake_run_tool(cmd, **kwargs):
        commands.append(cmd)
        return subprocess.CompletedProcess(cmd, 1, "", "stub")

    monkeypatch.setattr(md_pdf, "run_tool", fake_run_tool)
    md_pdf._pandoc_once("# Hi\n", tmp_path / "out.pdf", md_pdf.PANDOC_FROM, "header.tex", "/bin/mermaid-filter")

    cmd = commands[0]
    assert cmd.index("--lua-filter") < cmd.index("--filter")
