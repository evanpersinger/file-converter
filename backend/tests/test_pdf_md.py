"""Tests for the math and symbol normalization in pdf_md.py.

normalize_math() is the one piece of the PDF -> Markdown path that is pure text in,
text out, so it is testable without building a PDF fixture. The cases below are the
behaviours the module docstring promises: LaTeX commands become unicode, real LaTeX
math survives with only its delimiters normalized, and code spans are never touched.
"""

from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest

from pdf_md import (
    apply_scripts,
    find_scripts,
    normalize_math,
    pdf_to_markdown,
    strip_page_numbers,
    strip_repeated_headers,
)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (r"\alpha + \beta", "α + β"),
        (r"\Sigma and \Omega", "Σ and Ω"),
        (r"\infty", "∞"),
        (r"\rightarrow", "→"),
        (r"\forall x \in S", "∀ x ∈ S"),
    ],
)
def test_latex_commands_become_unicode(source: str, expected: str) -> None:
    assert normalize_math(source) == expected


@pytest.mark.parametrize(("source", "expected"), [(r"\leq", "≤"), (r"\geq", "≥")])
def test_longest_latex_command_wins(source: str, expected: str) -> None:
    """\\leq must be matched whole. If the shorter \\le were substituted first the
    trailing q would be stranded as "≤q"."""
    assert normalize_math(source) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("a <= b", "a ≤ b"),
        ("a >= b", "a ≥ b"),
        ("a != b", "a ≠ b"),
        ("a ~= b", "a ≈ b"),
        ("+/-", "±"),
        ("-/+", "∓"),
        ("a -> b", "a → b"),
    ],
)
def test_ascii_operators_become_unicode(source: str, expected: str) -> None:
    assert normalize_math(source) == expected


def test_long_dash_is_not_read_as_an_arrow() -> None:
    """The arrow rule has a lookbehind so ASCII art like --> is left as typed."""
    assert normalize_math("a --> b") == "a --> b"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("x^2", "x²"),
        ("x^{10}", "x¹⁰"),
        ("x^n", "xⁿ"),
        ("x^{-1}", "x⁻¹"),
        ("x_1", "x₁"),
        ("x_i", "xᵢ"),
        ("x_{ij}", "xᵢⱼ"),
    ],
)
def test_superscripts_and_subscripts_are_mapped(source: str, expected: str) -> None:
    assert normalize_math(source) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (r"\sigma^2", "σ²"),
        (r"\alpha_i", "αᵢ"),
        (r"\beta_i", "βᵢ"),
        (r"\mu^2", "μ²"),
        (r"\pi^2", "π²"),
        (r"\sum_{i=1}^n", "∑ᵢ₌₁ⁿ"),
        (r"\int_0^1", "∫₀¹"),
    ],
)
def test_superscript_subscript_after_latex_symbol_is_mapped(
    source: str, expected: str
) -> None:
    """The base-character check runs after \\sigma etc. are already substituted to
    unicode, so it must accept those unicode symbols too, not just ASCII."""
    assert normalize_math(source) == expected


def test_unmappable_script_falls_back_to_plain_form() -> None:
    """No unicode superscript exists for 'a' or 'b', so the whole run is left readable
    rather than half-converted."""
    assert normalize_math("x^{ab}") == "x^ab"


def test_bare_exponent_followed_by_another_word_is_left_alone() -> None:
    """x^ab is ambiguous without braces (exponent 'a' then word 'b', or exponent
    'ab'?), so it's left as typed rather than guessed at."""
    assert normalize_math("x^ab") == "x^ab"


def test_operator_bound_converts_even_glued_to_the_next_term() -> None:
    """\\sum_{i=1}^nw_i (issue #1): a PDF's raw text layer often has no space between
    an operator's upper bound and the term that follows it. Unlike the bare x^ab case
    above, a superscript chained right after a closing brace is unambiguously an
    operator bound, so it must still convert."""
    assert normalize_math(r"\sum_{i=1}^nw_i") == "∑ᵢ₌₁ⁿwᵢ"


def test_snake_case_identifier_is_left_alone() -> None:
    """Multi-letter subscripts need braces precisely so ordinary identifiers survive."""
    assert normalize_math("snake_case") == "snake_case"


def test_inline_code_is_not_touched() -> None:
    assert normalize_math("use `x_i` here") == "use `x_i` here"


def test_fenced_code_block_is_not_touched() -> None:
    source = "```\nx^2 and \\alpha\n```"
    assert normalize_math(source) == source


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (r"\(x^2\)", "$x^2$"),
        (r"\[E = mc^2\]", "$$E = mc^2$$"),
        ("$$a^2 + b^2$$", "$$a^2 + b^2$$"),
    ],
)
def test_latex_math_keeps_its_contents_and_normalizes_delimiters(
    source: str, expected: str
) -> None:
    """Inside math the LaTeX is left as LaTeX for a math-aware viewer to render, so
    x^2 must NOT come back as x²."""
    assert normalize_math(source) == expected


def test_currency_is_not_treated_as_math() -> None:
    """A single $..$ only counts as math when it contains \\, ^ or _."""
    assert normalize_math("costs $5 and $10 total") == "costs $5 and $10 total"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("𝜎", "σ"),
        ("𝑠 = 𝑥 + 𝑦", "s = x + y"),
        ("ℎ", "h"),
        ("𝜎^2", "σ²"),
    ],
)
def test_styled_math_letters_become_plain_letters(source: str, expected: str) -> None:
    """A typeset PDF's text layer holds math-italic letters (U+1D400 block), not plain ones."""
    assert normalize_math(source) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [("𝜎 [2]", "σ²"), ("𝑠 [2] = 𝜎", "s² = σ"), ("𝑥 [10]", "x¹⁰"), ("𝑥[2]", "x²")],
)
def test_bracketed_exponent_after_a_styled_letter_becomes_a_superscript(
    source: str, expected: str
) -> None:
    """pymupdf4llm writes an exponent as ' [2]' after its base."""
    assert normalize_math(source) == expected


def test_bracketed_number_after_a_word_is_left_alone() -> None:
    """After a word, [2] is a citation, not an exponent."""
    assert normalize_math("as shown by Smith [2]") == "as shown by Smith [2]"


def test_only_styled_math_letters_are_normalized() -> None:
    """NFKC would also flatten ligatures and superscripts, so it runs on the styled letters only."""
    source = "ﬁnal x² ½"
    assert normalize_math(source) == source


@pytest.mark.parametrize(("source", "expected"), [("x2", "x²"), ("n2", "n²")])
def test_ocr_mode_promotes_a_lone_trailing_digit(source: str, expected: str) -> None:
    assert normalize_math(source, ocr=True) == expected
    assert normalize_math(source, ocr=False) == source


@pytest.mark.parametrize("source", ["Table B2", "Q4 results", "cell A1"])
def test_ocr_mode_leaves_uppercase_labels(source: str) -> None:
    assert normalize_math(source, ocr=True) == source


@pytest.mark.parametrize("source", ["COVID19", "GPT4"])
def test_ocr_mode_leaves_digits_inside_words(source: str) -> None:
    assert normalize_math(source, ocr=True) == source


@pytest.mark.parametrize(
    ("source", "ocr_expected"),
    [
        ("a long day — and a longer night", "a long day - and a longer night"),
        ("Internet – it lacks a center", "Internet - it lacks a center"),
        ("pages 2745–2754", "pages 2745-2754"),
        ("x – y = 3", "x - y = 3"),
        ("fell to –5 degrees", "fell to -5 degrees"),
    ],
)
def test_dashes_are_kept_on_searchable_pages_and_flattened_by_ocr(
    source: str, ocr_expected: str
) -> None:
    """A dash in searchable prose is a real dash. Only OCR text, where a minus sign
    is often misread as one, gets it flattened to a hyphen."""
    assert normalize_math(source, ocr=False) == source
    assert normalize_math(source, ocr=True) == ocr_expected


@pytest.mark.parametrize("marker", ["3", "## 3", "## **3**", "**3**"])
def test_page_number_at_the_bottom_of_a_page_is_removed(marker: str) -> None:
    assert strip_page_numbers(f"Some body text.\n\n{marker}") == "Some body text."


def test_page_number_at_the_top_of_a_page_is_removed() -> None:
    assert strip_page_numbers("12\n\nSome body text.") == "Some body text."


@pytest.mark.parametrize(
    "line",
    [
        "1. Collect the raw data",
        "> 8 Smith (1999) himself describes a different approach.",
        "019239130213012391293129312913912391239",
        "12345",
        "|Metric|Q1|Q2|",
    ],
)
def test_edge_lines_that_are_real_content_are_kept(line: str) -> None:
    """Only a bare 1-4 digit line counts as a page number, not a list item, a footnote,
    a long digit string, or a table row."""
    source = f"Some body text.\n\n{line}"
    assert strip_page_numbers(source) == source


def test_digit_only_line_in_the_middle_of_a_page_is_kept() -> None:
    source = "\n".join(["one", "two", "three", "42", "four", "five", "six"])
    assert strip_page_numbers(source) == source


def test_running_header_is_kept_on_the_first_page_and_dropped_from_later_ones() -> None:
    pages = [
        "58 A. B. Author\n\nFirst page text.",
        "59 A. B. Author\n\nSecond page text.",
        "60 A. B. Author\n\nThird page text.",
    ]
    assert strip_repeated_headers(pages) == [
        "58 A. B. Author\n\nFirst page text.",
        "Second page text.",
        "Third page text.",
    ]


def test_running_footer_is_dropped_the_same_way() -> None:
    pages = [
        "First text.\n\nJournal of Medicine | Vol 42 | Page 17",
        "Second text.\n\nJournal of Medicine | Vol 42 | Page 18",
        "Third text.\n\nJournal of Medicine | Vol 42 | Page 19",
    ]
    assert strip_repeated_headers(pages) == [pages[0], "Second text.", "Third text."]


@pytest.mark.parametrize("repeated_line", ["|Metric|Q1|Q2|", "## Introduction"])
def test_repeated_table_rows_and_headings_are_kept(repeated_line: str) -> None:
    pages = [f"{repeated_line}\n\n{word} page text." for word in ("First", "Second", "Third")]
    assert strip_repeated_headers(pages) == pages


def test_line_repeated_on_fewer_than_three_pages_is_kept() -> None:
    pages = ["Shared line\n\nFirst page text.", "Shared line\n\nSecond page text.", "Third page text."]
    assert strip_repeated_headers(pages) == pages


def test_repeated_line_in_the_middle_of_a_page_is_kept() -> None:
    pages = [
        "\n".join([f"{w} a", f"{w} b", f"{w} c", "Shared line", f"{w} d", f"{w} e", f"{w} f"])
        for w in ("first", "second", "third")
    ]
    assert strip_repeated_headers(pages) == pages


@pytest.mark.parametrize("source", ["", None])
def test_falsy_input_is_returned_unchanged(source: str | None) -> None:
    assert normalize_math(source) == source


def test_normalization_is_idempotent() -> None:
    """Re-running over already-converted text must not double-convert, since a
    document can pass through this path more than once."""
    source = r"\alpha x^2 <= \beta and `x_i` stays"
    once = normalize_math(source)
    assert normalize_math(once) == once


def test_each_page_starts_with_a_page_marker(tmp_path: Path) -> None:
    pdf_path = tmp_path / "two_pages.pdf"
    doc = fitz.open()
    for text in (
        "The first page has enough text to count as searchable.",
        "The second page also has enough text to be searchable.",
    ):
        doc.new_page().insert_text((72, 72), text)
    doc.save(pdf_path)
    doc.close()

    markdown = pdf_to_markdown(str(pdf_path))

    assert markdown.index("<!-- page 1 -->") < markdown.index("first page")
    assert markdown.index("first page") < markdown.index("<!-- page 2 -->")
    assert markdown.index("<!-- page 2 -->") < markdown.index("second page")


def test_running_header_is_kept_once_in_the_converted_output(tmp_path: Path) -> None:
    pdf_path = tmp_path / "three_pages.pdf"
    doc = fitz.open()
    for i, name in enumerate(("Alpha", "Bravo", "Charlie")):
        page = doc.new_page()
        page.insert_text((72, 40), f"{58 + i} A. B. Author")
        page.insert_text((72, 300), f"{name} page has enough text to count as searchable.")
    doc.save(pdf_path)
    doc.close()

    markdown = pdf_to_markdown(str(pdf_path))

    assert markdown.count("A. B. Author") == 1
    for name in ("Alpha", "Bravo", "Charlie"):
        assert name in markdown


def _doc_with(*parts: tuple[float, float, float, str]) -> fitz.Document:
    """A one-page PDF with each (x, y, font size, text) drawn where it says."""
    doc = fitz.open()
    page = doc.new_page()
    for x, y, size, text in parts:
        page.insert_text((x, y), text, fontsize=size)
    return doc


@pytest.mark.parametrize(
    ("parts", "expected"),
    [
        ([(72, 100, 10, "x"), (78, 96, 7, "2")], [("x", "2", "sup")]),
        ([(72, 100, 10, "x"), (78, 103, 7, "1")], [("x", "1", "sub")]),
        ([(72, 100, 10, "is x"), (88, 96, 7, "2")], [(" x", "2", "sup")]),
    ],
)
def test_find_scripts_reads_a_small_raised_or_lowered_span(parts, expected) -> None:
    assert find_scripts(_doc_with(*parts)[0]) == expected


@pytest.mark.parametrize(
    "parts",
    [
        [(72, 100, 10, "x"), (78, 96, 10, "y")],
        [(72, 100, 10, "x"), (78, 100, 7, "note")],
    ],
    ids=["raised but the same size", "smaller but on the same baseline"],
)
def test_find_scripts_needs_a_span_to_be_both_smaller_and_shifted(parts) -> None:
    assert find_scripts(_doc_with(*parts)[0]) == []


def test_find_scripts_skips_spans_stacked_over_each_other() -> None:
    """The bounds of a sum sit above and below each other, they are not exponents.

    fitz puts hand-drawn stacked text on separate lines, so the line is built by hand in
    the shape get_text("dict") returns (the numbers come from a pandoc-made PDF).
    """

    def span(text: str, x: float, y: float, size: float) -> dict:
        return {"text": text, "size": size, "origin": (x, y), "bbox": (x, y - size, x + 5, y)}

    line = {"spans": [span("∑", 278.5, 134.8, 9.96), span("𝑛", 289.0, 129.0, 6.97), span("𝑖=1", 289.0, 138.6, 6.97)]}
    page = SimpleNamespace(get_text=lambda kind: {"blocks": [{"lines": [line]}]})

    assert find_scripts(page) == []


@pytest.mark.parametrize(
    ("text", "scripts", "expected"),
    [
        ("s [2] = 1", [("s", "2", "sup")], "s² = 1"),
        ("(𝑋−𝜇) [2] ]", [("𝜇)", "2", "sup")], "(𝑋−𝜇)² ]"),
        ("x1 and x2", [("x", "1", "sub"), ("x", "2", "sub")], "x₁ and x₂"),
        ("box 2", [("x", "2", "sup")], "box 2"),
        ("x12", [("x", "1", "sub")], "x12"),
        ("nothing to find", [("x", "2", "sup")], "nothing to find"),
    ],
    ids=["bracketed", "after a paren", "inline subscripts", "prose with a space", "longer number", "not found"],
)
def test_apply_scripts_rewrites_only_the_scripts_it_was_told_about(text, scripts, expected) -> None:
    assert apply_scripts(text, scripts) == expected


def test_apply_scripts_rewrites_a_repeat_no_more_often_than_the_pdf_has_it() -> None:
    assert apply_scripts("x2 and x2", [("x", "2", "sup")]) == "x² and x2"


def test_a_raised_digit_after_a_paren_becomes_a_superscript(tmp_path: Path) -> None:
    """The geometry pass reaches what the ' [2]' rule cannot: here the base is a ')'."""
    pdf_path = tmp_path / "paren_square.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "The squared difference is (a-b)", fontsize=10)
    page.insert_text((72 + fitz.get_text_length("The squared difference is (a-b)", fontsize=10), 96), "2", fontsize=7)
    doc.save(pdf_path)
    doc.close()

    assert "(a-b)²" in pdf_to_markdown(str(pdf_path))
