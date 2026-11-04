"""Tests for pdf_fonts.py, the shared Unicode font setup for the reportlab converters."""

import pytest

import pdf_fonts


def test_without_any_font_file_the_built_in_fonts_are_used(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdf_fonts, "_CANDIDATES", {role: [] for role in pdf_fonts._CANDIDATES})
    pdf_fonts.fonts.cache_clear()
    try:
        fonts = pdf_fonts.fonts()
        assert (fonts.sans, fonts.sans_bold, fonts.mono, fonts.fallback) == (
            "Helvetica", "Helvetica-Bold", "Courier", None
        )
        # Built-in fonts cover cp1252 only, same limit as before.
        assert fonts.undrawable("café €", fonts.sans) == []
        assert fonts.undrawable("中文 ж", fonts.sans) == ["中", "文", "ж"]
    finally:
        pdf_fonts.fonts.cache_clear()


def test_markup_escapes_and_wraps_runs_in_the_fallback_font() -> None:
    fonts = pdf_fonts.Fonts(
        sans="S", sans_bold="SB", mono="M", fallback="F",
        _coverage={"S": frozenset(map(ord, "ab <&>")), "F": frozenset(map(ord, "中文"))},
    )

    assert fonts.markup("a <b> 中文 & a", "S") == 'a &lt;b&gt; <font name="F">中文</font> &amp; a'
    assert fonts.undrawable("a中x", "S") == ["x"]
