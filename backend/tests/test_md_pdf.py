"""Tests for the Markdown preprocessing in md_pdf.py.

Pandoc and xelatex are not under test, and neither is reachable from a unit test
anyway. What is testable is everything that runs before them: the unicode -> LaTeX
maps, the delimiter normalization, and the code-protection that has to survive all of
it. These are the inverse of pdf_md.py's, so the last section checks the pair lines up.
"""

from pathlib import Path

import pytest

from external_tool import ToolTimeout
from md_pdf import (
    _convert_paren_math_to_dollars,
    _is_ascii_diagram_line,
    clean_control_chars,
    convert_md_to_pdf,
    convert_symbols,
    ensure_list_spacing,
    normalize_math_delimiters,
    normalize_tables,
    run_pandoc,
    wrap_ascii_diagrams,
)
from pdf_md import normalize_math


# Unicode -> LaTeX


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("α", r"$\alpha$"),
        ("Ω", r"$\Omega$"),
        ("∑", r"$\sum$"),
        ("∞", r"$\infty$"),
        ("∀", r"$\forall$"),
        ("∴", r"$\therefore$"),
        ("∵", r"$\because$"),
    ],
)
def test_greek_and_operators_become_latex_commands(source: str, expected: str) -> None:
    assert convert_symbols(source) == expected


@pytest.mark.parametrize("symbol", ["≤", "≥", "±", "≈"])
def test_some_symbols_stay_unicode_but_move_into_math_mode(symbol: str) -> None:
    """UNICODE_MATH_KEEP exists because these render better as the raw character than
    as a LaTeX command, but they still have to sit inside $..$ to render at all."""
    assert convert_symbols(symbol) == f"${symbol}$"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("x²", r"$x^{2}$"),
        ("x⁻¹", r"$x^{-1}$"),
        ("xᵢ", r"$x_{i}$"),
        ("x₁₂", r"$x_{12}$"),
        ("Qᵀ", r"$Q^{T}$"),
        ("J = Qᵀe", r"J = $Q^{T}$e"),
    ],
)
def test_unicode_scripts_become_latex_scripts(source: str, expected: str) -> None:
    assert convert_symbols(source) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("t₀.₉₇₅,₁₀", r"$t_{0.975,10}$"),
        ("F₀.₀₅,₁,₁₀", r"$F_{0.05,1,10}$"),
        ("x₁,₂", r"$x_{1,2}$"),
        ("β̂₀.₅", r"$\hat{\beta}_{0.5}$"),
    ],
)
def test_a_subscript_can_contain_a_decimal_point_or_comma(source: str, expected: str) -> None:
    """There is no unicode subscript "." or ",", so the run used to stop after the first
    digit and the rest was left as raw characters the font cannot draw."""
    assert convert_symbols(source) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("x₁, x₂", r"$x_{1}$, $x_{2}$"),
        ("H₀.", r"$H_{0}$."),
        ("a₁.b", r"$a_{1}$.b"),
    ],
)
def test_punctuation_next_to_a_subscript_stays_outside_it(source: str, expected: str) -> None:
    assert convert_symbols(source) == expected


def test_a_greek_base_keeps_its_command_under_a_subscript() -> None:
    """The base is looked up in GREEK_TO_LATEX before the script is attached, so this
    must not come out as a literal theta character wrapped in math mode."""
    assert convert_symbols("θ₀") == r"$\theta_{0}$"


def test_a_barred_variable_becomes_a_bar_command() -> None:
    assert convert_symbols("x̄") == r"$\bar{x}$"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("β̂₁", r"$\hat{\beta}_{1}$"),
        ("β̂₀", r"$\hat{\beta}_{0}$"),
        ("β̂", r"$\hat{\beta}$"),
    ],
)
def test_a_hatted_variable_keeps_its_hat_and_subscript(source: str, expected: str) -> None:
    assert convert_symbols(source) == expected


def test_a_bare_greek_command_in_prose_is_wrapped_in_math_mode() -> None:
    assert convert_symbols(r"the slope \beta is estimated") == r"the slope $\beta$ is estimated"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (r"\beta_1", r"$\beta_1$"),
        (r"\beta_{10}", r"$\beta_{10}$"),
        (r"\hat\beta_1", r"$\hat\beta_1$"),
        (r"\hat{\beta}_1", r"$\hat{\beta}_1$"),
        (r"t_{0.975,10}", r"$t_{0.975,10}$"),
    ],
)
def test_a_typed_command_or_braced_subscript_is_wrapped_with_its_script(source: str, expected: str) -> None:
    """\\hat outside math is a LaTeX error that sends the whole document to safe mode, and
    a script left outside the $..$ prints as literal text."""
    assert convert_symbols(source) == expected


@pytest.mark.parametrize("source", ["snake_case_name", "file_1.txt", "x_1"])
def test_underscores_in_ordinary_text_are_left_alone(source: str) -> None:
    assert convert_symbols(source) == source


def test_a_greek_command_already_in_math_mode_is_not_wrapped_again() -> None:
    assert convert_symbols(r"$\hat{\beta}_1$ and $$\beta$$") == r"$\hat{\beta}_1$ and $$\beta$$"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("√(MSE / Sxx)", r"$\sqrt{MSE / Sxx}$"),
        ("√((a + b) / c)", r"$\sqrt{(a + b) / c}$"),
        ("√(σ²)", r"$\sqrt{\sigma^{2}}$"),
        ("√2", r"$\sqrt{2}$"),
        ("$√(x)$", r"$\sqrt{x}$"),
    ],
)
def test_a_square_root_wraps_its_argument(source: str, expected: str) -> None:
    """A lone \\surd sits below the baseline with no bar, so √ has to become \\sqrt{..}."""
    assert convert_symbols(source) == expected


def test_touching_symbols_become_one_span_not_a_double_dollar() -> None:
    assert convert_symbols("aᵢbⱼ") == "$a_{i}b_{j}$"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("∑xᵢ", r"$\sum x_{i}$"),
        ("∫xᵢ", r"$\int x_{i}$"),
        ("αxᵢ", r"$\alpha x_{i}$"),
        ("Σeᵢxᵢ", r"$\Sigma e_{i}x_{i}$"),
    ],
)
def test_a_symbol_right_before_a_script_is_still_converted(source: str, expected: str) -> None:
    """The script step puts a $ right after the symbol, which used to make the symbol
    pass skip it and leave a raw character the font cannot draw."""
    assert convert_symbols(source) == expected


def test_a_converted_symbol_touching_a_span_does_not_skip_later_symbols() -> None:
    """Wrapping the Σ next to $e_{i}$ makes a touching "$$" for a moment. If it survives,
    the math count flips and every symbol after it is left raw."""
    assert convert_symbols("Σeᵢ and ∑ x and ∫ x") == r"$\Sigma e_{i}$ and $\sum$ x and $\int$ x"


@pytest.mark.parametrize("source", ["$α + β$ here", "$$Σ x$$", "$x$ and $α$"])
def test_symbols_already_inside_math_are_left_alone(source: str) -> None:
    assert convert_symbols(source) == source


def test_touching_symbols_do_not_strip_spaces_on_later_lines() -> None:
    """eᵢxᵢ used to leave "$e_{i}$$x_{i}$", the "$$" shifted the $-pairing, and every
    later span lost the spaces (and blank lines) around it."""
    result = convert_symbols("eᵢxᵢ = 0\n\nthe slope \\beta is $\\gamma$ and $\\delta$ too.\n\n$x^2$ $x_n$")
    assert "the slope $\\beta$ is $\\gamma$ and $\\delta$ too.\n\n$x^2$" in result


def test_a_display_math_block_is_not_merged_with_inline_math() -> None:
    assert convert_symbols("$$y = x$$ and $a$ and $b$") == "$$y = x$$ and $a$ and $b$"


def test_adjacent_math_blocks_are_merged() -> None:
    """Converting symbols one at a time leaves a run of separate $..$ blocks, which
    xelatex sets with visible gaps. They get folded back into one."""
    assert convert_symbols("$a$ + $b$") == "$a + b$"
    assert convert_symbols("$a$ - $b$") == "$a - b$"


@pytest.mark.parametrize("source", [
    "- $a = 1$\n\n- $b = 2$",
    "- $a$\n- $b$",
    "+ $a$\n+ $b$",
])
def test_math_only_bullets_are_not_merged_into_one(source: str) -> None:
    """The merge used to cross the newline and read the list dash as a minus sign."""
    assert convert_symbols(source) == source


# Code protection


def test_inline_code_is_not_touched() -> None:
    assert convert_symbols("use `x_i` and `α` here") == "use `x_i` and `α` here"


def test_fenced_code_block_is_not_touched() -> None:
    source = "```\nα = x²\n```"
    assert convert_symbols(source) == source


# Delimiters


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (r"\[x + y\]", "$$x + y$$"),
        (r"\(x + y\)", "$x + y$"),
    ],
)
def test_latex_delimiters_are_normalized_to_dollars(source: str, expected: str) -> None:
    """raw_tex does not reliably handle \\[..\\], so both forms are rewritten to the
    dollar syntax pandoc's tex_math_dollars actually reads."""
    assert normalize_math_delimiters(source) == expected


@pytest.mark.parametrize(("dash", "source"), [("—", "a — b"), ("–", "a – b")])
def test_em_and_en_dashes_are_flattened(dash: str, source: str) -> None:
    assert normalize_math_delimiters(source) == "a - b"


def test_space_after_an_opening_dollar_is_trimmed() -> None:
    """tex_math_dollars requires the opening $ to be followed by a non-space, or the
    block is not read as math at all."""
    assert normalize_math_delimiters(r"$ \alpha$") == r"$\alpha$"


# Control characters and list spacing


@pytest.mark.parametrize(("source", "expected"), [("a\x0bb", "a\nb"), ("a\x0cb", "a\nb")])
def test_vertical_whitespace_controls_become_newlines(source: str, expected: str) -> None:
    assert clean_control_chars(source) == expected


def test_other_control_characters_are_stripped() -> None:
    assert clean_control_chars("a\x07b\x1fc") == "abc"


def test_tabs_and_newlines_survive() -> None:
    assert clean_control_chars("a\tb\nc") == "a\tb\nc"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("text\n- item", "text\n\n- item"),
        ("text\n* item", "text\n\n* item"),
        ("text\n1. item", "text\n\n1. item"),
    ],
)
def test_a_blank_line_is_inserted_before_a_list(source: str, expected: str) -> None:
    """Without the blank line pandoc reads the list as a continuation of the paragraph."""
    assert ensure_list_spacing(source) == expected


def test_an_already_spaced_list_is_left_alone() -> None:
    source = "text\n\n- item"
    assert ensure_list_spacing(source) == source


# Round trip against pdf_md.py


@pytest.mark.parametrize(
    ("latex", "unicode_form", "back_to_latex"),
    [
        (r"\alpha", "α", r"$\alpha$"),
        (r"\Omega", "Ω", r"$\Omega$"),
        (r"\sum", "∑", r"$\sum$"),
        ("x^2", "x²", r"$x^{2}$"),
        ("x_i", "xᵢ", r"$x_{i}$"),
    ],
)
def test_the_two_directions_line_up(
    latex: str, unicode_form: str, back_to_latex: str
) -> None:
    """pdf_md maps LaTeX down to unicode and md_pdf maps it back up. A symbol added to
    one table without the other silently breaks a pdf -> md -> pdf round trip, and this
    is the test that catches it."""
    assert normalize_math(latex) == unicode_form
    assert convert_symbols(unicode_form) == back_to_latex


# ASCII diagrams


@pytest.mark.parametrize(
    "line",
    [
        "A --> B",
        "A <-- B",
        "|        |         |",
        "5        |         8",
        "1        6         3",
    ],
)
def test_diagram_lines_are_recognized(line: str) -> None:
    assert _is_ascii_diagram_line(line) is True


@pytest.mark.parametrize(
    "line",
    [
        "",
        "This is a sentence.",
        "1 2 3",
        "| a | b |",
        "|---|---|",
    ],
)
def test_prose_and_ordinary_table_rows_are_not_diagram_lines(line: str) -> None:
    """'1 2 3' is the near-miss worth pinning: it is digits and spaces, but the gaps
    are single spaces, so it is a sentence rather than positioned edge weights."""
    assert _is_ascii_diagram_line(line) is False


def test_a_diagram_block_is_wrapped_in_a_fence() -> None:
    """Unfenced, pandoc collapses the runs of spaces and the diagram falls apart."""
    assert wrap_ascii_diagrams("A --> B\nB --> C") == "```\nA --> B\nB --> C\n```"


def test_a_lone_diagram_line_is_left_alone() -> None:
    """One line is more likely a sentence containing an arrow than a diagram, so the
    block has to be at least two lines before it gets fenced."""
    assert wrap_ascii_diagrams("A --> B") == "A --> B"


def test_an_existing_code_fence_is_not_double_wrapped() -> None:
    source = "```\nA --> B\nB --> C\n```"
    assert wrap_ascii_diagrams(source) == source


def test_a_numeric_markdown_table_survives() -> None:
    """A table whose cells are all numbers looks exactly like a diagram to the
    heuristic: strip the pipes, spaces and digits and nothing is left. Wrapping its
    data rows in a fence splits the table away from its own header."""
    source = "| a | b |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |"
    assert wrap_ascii_diagrams(source) == source


# Symbols outside the maps


@pytest.mark.parametrize("source", ["a ⨁ b", "ℵ", "a ⊗ b"])
def test_unmapped_symbols_pass_through_untouched(source: str) -> None:
    """Nothing in the maps matches these, and guessing a LaTeX command for them would
    be worse than leaving the character for the font to handle."""
    assert convert_symbols(source) == source


def test_an_uncommon_but_mapped_operator_still_converts() -> None:
    assert convert_symbols("⋈") == r"$\bowtie$"


def test_a_superscript_outside_the_map_is_left_alone() -> None:
    assert convert_symbols("xᵃ") == "xᵃ"


def test_a_partly_mappable_script_run_converts_only_the_mappable_part() -> None:
    """Note this is the opposite of pdf_md's rule, where _map_chars refuses to convert
    a run at all unless every character in it maps. Here the run is split."""
    assert convert_symbols("x²ᵃ") == r"$x^{2}$ᵃ"


# A hung pandoc


def test_a_pandoc_timeout_is_not_retried_in_safe_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A render that hung would most likely hang again, and the retry would double the wait."""
    calls = []

    def hung(*args, **kwargs):
        calls.append(1)
        raise ToolTimeout("pandoc took longer than 300 seconds")

    monkeypatch.setattr("md_pdf._pandoc_once", hung)

    assert run_pandoc("# hi", "# hi", tmp_path / "out.pdf", "hi.md") is False
    assert len(calls) == 1


# A $ that is plain text (a price)


@pytest.mark.parametrize(("source", "expected"), [
    ("cost $5 and α here", r"cost \$5 and $\alpha$ here"),
    ("costs $5 and $10, with α and β here", r"costs \$5 and \$10, with $\alpha$ and $\beta$ here"),
    ("Price $5.\n\nLater β and ∑xᵢ here", "Price \\$5.\n\nLater $\\beta$ and $\\sum x_{i}$ here"),
    ("$5 and $x$ α", r"\$5 and $x$ $\alpha$"),
    (r"x \$ y α", r"x \$ y $\alpha$"),
])
def test_a_dollar_that_is_text_does_not_throw_off_symbol_conversion(source: str, expected: str) -> None:
    """Follows pandoc's tex_math_dollars rule: "$5 and $10" is text, not a math span."""
    assert convert_symbols(source) == expected


@pytest.mark.parametrize("source", [
    "$a$ and $b$",
    "$$x$$",
    "$$a\nb$$ then $c$",
    "`$5` and `$x$`",
    "~~~\nPRICE=$5\n~~~",
    "Run:\n\n    echo $HOME\n\nDone.",
    "The fit has $r$² of 0.9",
])
def test_real_math_and_code_dollars_are_unchanged(source: str) -> None:
    assert convert_symbols(source) == source


# Tables

# What normalize_tables puts in front of a table, and after it once the text resumes
BEFORE_TABLE = "\n\\nopagebreak[4]\n\n"
AFTER_TABLE = "\\nopagebreak[4]\n\n"


def test_a_table_is_guarded_against_page_breaks() -> None:
    result = normalize_tables("| a | b |\n|---|---|\n| 1 | 2 |")

    assert result == BEFORE_TABLE + "| a | b |\n| --- | --- |\n| 1 | 2 |"


def test_pipe_spacing_is_normalized() -> None:
    result = normalize_tables("|a|b|\n|--|--|\n|1|2|")

    assert result == BEFORE_TABLE + "| a | b |\n| -- | -- |\n| 1 | 2 |"


def test_column_alignment_colons_survive() -> None:
    result = normalize_tables("| a | b | c |\n|:--|:-:|--:|\n| 1 | 2 | 3 |")

    assert "| :-- | :-: | --: |" in result


def test_the_guard_is_closed_when_text_resumes() -> None:
    result = normalize_tables("| a |\n|---|\n| 1 |\nafter")

    assert result.endswith("| 1 |\n" + AFTER_TABLE + "after")


def test_text_before_a_table_gets_a_blank_line_so_pandoc_sees_the_table() -> None:
    result = normalize_tables("before\n| a |\n|---|\n| 1 |")

    assert result.startswith("before\n" + BEFORE_TABLE + "| a |")


def test_every_table_gets_its_own_guard() -> None:
    result = normalize_tables("| a |\n|---|\n| 1 |\n\n| b |\n|---|\n| 2 |")

    assert BEFORE_TABLE + "| a |" in result
    assert BEFORE_TABLE + "| b |" in result


@pytest.mark.parametrize("source", [
    "```\n| a | b |\n|---|---|\n```",
    "$$\n| a | b |\n$$",
    "a | b",
    "",
])
def test_text_that_is_not_a_table_is_left_alone(source: str) -> None:
    """Rows inside a code fence or a $$ block are not tables, and a pipe in the middle of
    a line is not a row."""
    assert normalize_tables(source) == source


def test_paren_math_in_a_cell_becomes_dollar_math() -> None:
    result = normalize_tables("| \\(x\\) | b |\n|---|---|\n| 1 | 2 |")

    assert "| $x$ | b |" in result


def test_adjacent_math_in_a_cell_is_combined_into_one_span() -> None:
    result = normalize_tables("| a |\n|---|\n| $d_i$ = $y_i$ - $x_i$ |")

    assert result.endswith("| $d_i = y_i - x_i$ |")


@pytest.mark.parametrize(("cell", "expected"), [
    ("-5", "\\mbox{-5}"),
    ("$-5$", "$-5$"),
    ("x = -5 and $-6$", "x = \\mbox{-5} and $-6$"),
])
def test_a_negative_number_is_kept_whole_but_not_inside_math(cell: str, expected: str) -> None:
    """A line break between the minus and the digits would read as a different number."""
    result = normalize_tables(f"| a |\n|---|\n| {cell} |")

    assert result.endswith(f"| {expected} |")


def test_a_header_row_narrower_than_the_table_becomes_a_centered_caption() -> None:
    """A row with fewer cells than the table under it breaks the table parser."""
    result = normalize_tables("| Title |\n| a | b | c | d |\n|---|---|---|---|\n| 1 | 2 | 3 | 4 |")

    assert result == (
        BEFORE_TABLE
        + "\\begin{center}\\textbf{Title}\\end{center}\n\n"
        + "| a | b | c | d |\n| --- | --- | --- | --- |\n| 1 | 2 | 3 | 4 |"
    )


def test_a_caption_has_its_latex_characters_escaped() -> None:
    result = normalize_tables("| A_1 & 50% |\n| a | b | c | d |\n|---|---|---|---|")

    assert "\\textbf{A\\_1 \\& 50\\%}" in result


def test_a_row_only_one_cell_shorter_is_not_a_caption() -> None:
    """The next row has to be at least two cells wider, or it is just a ragged table."""
    result = normalize_tables("| a |\n| b | c |\n|---|---|")

    assert "\\begin{center}" not in result


def test_a_price_in_a_cell_keeps_its_escape_through_the_symbol_pass() -> None:
    """normalize_tables drops the backslash, and convert_symbols has to put it back, or the
    $ could pair with another one in the row."""
    result = convert_symbols(normalize_tables("| a | b |\n|---|---|\n| \\$5 | \\$10 |"))

    assert result.endswith("| \\$5 | \\$10 |")


def test_a_symbol_in_a_cell_is_converted_after_the_table_is_normalized() -> None:
    result = convert_symbols(normalize_tables("|a|\n|-|\n|α|"))

    assert result.endswith("| $\\alpha$ |")


@pytest.mark.parametrize(("source", "expected"), [
    (r"\(x\)", "$x$"),
    (r"\(a\) and \(b\)", "$a$ and $b$"),
    (r"if \(x > 1\) then", "if $x > 1$ then"),
    (r"\(a \(b\) c\)", r"$a \(b\) c$"),
    (r"\(a", r"\(a"),
    ("plain", "plain"),
])
def test_paren_math_is_converted_with_its_nesting_honored(source: str, expected: str) -> None:
    assert _convert_paren_math_to_dollars(source) == expected


# Math delimiters, the rest of normalize_math_delimiters


@pytest.mark.parametrize(("source", "expected"), [
    ("\\[\nx + y\n\\]", "$$\nx + y\n$$"),
    ("\\[a\\] text \\[b\\]", "$$a$$ text $$b$$"),
    ("\\(  x + y  \\)", "$x + y$"),
    ("\\(a\\) and \\(b\\)", "$a$ and $b$"),
    ("\\(a +\nb\\)", "$a +\nb$"),
])
def test_latex_delimiters_are_converted_wherever_they_sit(source: str, expected: str) -> None:
    """A display block can span lines, each pair is matched on its own, and the padding
    inside \\( \\) is trimmed because pandoc will not read a padded span as math."""
    assert normalize_math_delimiters(source) == expected


@pytest.mark.parametrize("source", [r"\(a", r"\[a"])
def test_an_unclosed_latex_delimiter_is_left_alone(source: str) -> None:
    assert normalize_math_delimiters(source) == source


@pytest.mark.parametrize(("source", "expected"), [
    (r"\$\alpha + 1\$", r"$\alpha + 1$"),
    (r"\$ \alpha \$", r"$\alpha$"),
    (r"\$ \alpha + 1$", r"$\alpha + 1$"),
    (r"\$ x = \frac{1}{2}$", r"$x = \frac{1}{2}$"),
    ("$x\\$", "$x$"),
    ("$x_{1}\\$", "$x_{1}$"),
])
def test_escaped_dollars_around_real_math_become_delimiters(source: str, expected: str) -> None:
    """Pasted text often escapes the dollars of a math span. When what sits between them
    is math, they have to be real delimiters or the span prints raw."""
    assert normalize_math_delimiters(source) == expected


@pytest.mark.parametrize("source", [r"cost \$5", r"\$5 and \$10"])
def test_an_escaped_price_stays_escaped(source: str) -> None:
    """Two escaped dollars are not a math span unless the text between them is math."""
    assert normalize_math_delimiters(source) == source


def test_space_after_an_opening_dollar_is_trimmed_before_an_equation() -> None:
    assert normalize_math_delimiters("$ x = 1$") == "$x = 1$"


def test_padded_display_math_is_left_alone() -> None:
    """The trim rules must not eat into a $$ delimiter."""
    assert normalize_math_delimiters(r"$$ \alpha $$") == r"$$ \alpha $$"


@pytest.mark.parametrize(("source", "expected"), [
    ("```\na — b\n```", "```\na - b\n```"),
    ("$a – b$", "$a - b$"),
])
def test_dashes_are_flattened_in_code_and_in_math_too(source: str, expected: str) -> None:
    """Deliberate, since a long dash can break LaTeX, but it does reach inside code."""
    assert normalize_math_delimiters(source) == expected


@pytest.mark.parametrize("source", [
    "\\[\nx + y\n\\]",
    "\\(  x + y  \\)",
    r"\$ \alpha \$",
    r"\$5 and \$10",
    "$x\\$",
    "$ x = 1$",
    "$a — b$",
    "nothing to do",
])
def test_normalizing_twice_changes_nothing(source: str) -> None:
    once = normalize_math_delimiters(source)

    assert normalize_math_delimiters(once) == once


# convert_md_to_pdf, with pandoc replaced

WorkDirs = tuple[Path, Path]
PandocCalls = list[dict[str, object]]


@pytest.fixture
def pandoc_calls(monkeypatch: pytest.MonkeyPatch) -> PandocCalls:
    """Stand in for pandoc: run_pandoc records what it was handed and succeeds, and the
    pandoc lookup finds it, so none of these tests needs pandoc installed."""
    calls: PandocCalls = []

    def fake_run_pandoc(rich_md: str, safe_md: str, output_path: Path, input_name: str) -> bool:
        calls.append({"rich": rich_md, "safe": safe_md, "output": output_path, "name": input_name})
        return True

    monkeypatch.setattr("md_pdf.run_pandoc", fake_run_pandoc)
    monkeypatch.setattr("md_pdf.which", lambda name: f"/usr/bin/{name}")
    return calls


def write_md(folder: Path, name: str, text: str = "hello\n") -> Path:
    path = folder / name
    path.write_text(text, encoding="utf-8")
    return path


def test_the_pdf_is_named_after_the_markdown_file(
    work_dirs: WorkDirs, pandoc_calls: PandocCalls
) -> None:
    input_dir, output_dir = work_dirs
    write_md(input_dir, "notes.md")

    assert convert_md_to_pdf("notes.md", None, input_dir, output_dir) is True

    assert len(pandoc_calls) == 1
    assert pandoc_calls[0]["output"] == output_dir / "notes.pdf"
    assert pandoc_calls[0]["name"] == "notes.md"


def test_the_output_name_can_be_chosen_and_loses_any_folder(
    work_dirs: WorkDirs, pandoc_calls: PandocCalls
) -> None:
    input_dir, output_dir = work_dirs
    write_md(input_dir, "notes.md")

    convert_md_to_pdf("notes.md", "sub/renamed.pdf", input_dir, output_dir)

    assert pandoc_calls[0]["output"] == output_dir / "renamed.pdf"


def test_an_absolute_path_is_used_as_it_is(
    work_dirs: WorkDirs, pandoc_calls: PandocCalls, tmp_path: Path
) -> None:
    input_dir, output_dir = work_dirs
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    source = write_md(elsewhere, "abs.md")

    assert convert_md_to_pdf(str(source), None, input_dir, output_dir) is True

    assert pandoc_calls[0]["name"] == "abs.md"
    assert pandoc_calls[0]["output"] == output_dir / "abs.pdf"


def test_the_output_folder_is_created(work_dirs: WorkDirs, pandoc_calls: PandocCalls) -> None:
    input_dir, output_dir = work_dirs
    write_md(input_dir, "notes.md")

    convert_md_to_pdf("notes.md", None, input_dir, output_dir)

    assert output_dir.is_dir()


def test_a_pdf_path_is_refused(
    work_dirs: WorkDirs, pandoc_calls: PandocCalls, capsys: pytest.CaptureFixture[str]
) -> None:
    input_dir, output_dir = work_dirs

    assert convert_md_to_pdf("doc.pdf", None, input_dir, output_dir) is False

    assert "already in pdf format" in capsys.readouterr().out
    assert pandoc_calls == []


def test_a_missing_file_is_reported_and_pandoc_is_not_run(
    work_dirs: WorkDirs, pandoc_calls: PandocCalls, capsys: pytest.CaptureFixture[str]
) -> None:
    input_dir, output_dir = work_dirs

    assert convert_md_to_pdf("ghost.md", None, input_dir, output_dir) is False

    assert "not found" in capsys.readouterr().out
    assert pandoc_calls == []


def test_a_missing_pandoc_is_reported(
    work_dirs: WorkDirs,
    pandoc_calls: PandocCalls,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_dir, output_dir = work_dirs
    write_md(input_dir, "notes.md")
    monkeypatch.setattr("md_pdf.which", lambda name: None)

    assert convert_md_to_pdf("notes.md", None, input_dir, output_dir) is False

    assert "pandoc not found" in capsys.readouterr().out
    assert pandoc_calls == []


def test_both_texts_get_the_shared_delimiter_and_list_fixes(
    work_dirs: WorkDirs, pandoc_calls: PandocCalls
) -> None:
    """The safe text is what the fallback renders, so it needs the fixes that keep math
    and lists readable, just without the LaTeX the full render injects."""
    input_dir, output_dir = work_dirs
    write_md(input_dir, "notes.md", "text\n- item\n\n\\(x\\)\n")

    convert_md_to_pdf("notes.md", None, input_dir, output_dir)

    for text in (pandoc_calls[0]["rich"], pandoc_calls[0]["safe"]):
        assert "text\n\n- item" in text
        assert "$x$" in text


def test_only_the_rich_text_gets_symbol_and_table_rewrites(
    work_dirs: WorkDirs, pandoc_calls: PandocCalls
) -> None:
    input_dir, output_dir = work_dirs
    write_md(input_dir, "notes.md", "x² here\n\n| a |\n|---|\n| 1 |\n")

    convert_md_to_pdf("notes.md", None, input_dir, output_dir)

    rich, safe = pandoc_calls[0]["rich"], pandoc_calls[0]["safe"]
    assert "$x^{2}$" in rich and "\\nopagebreak" in rich
    assert "x²" in safe and "\\nopagebreak" not in safe


def test_control_characters_are_cleaned_from_both_texts(
    work_dirs: WorkDirs, pandoc_calls: PandocCalls
) -> None:
    input_dir, output_dir = work_dirs
    write_md(input_dir, "notes.md", "a\x07b\n")

    convert_md_to_pdf("notes.md", None, input_dir, output_dir)

    assert "ab" in pandoc_calls[0]["rich"] and "ab" in pandoc_calls[0]["safe"]
    assert "\x07" not in pandoc_calls[0]["rich"] and "\x07" not in pandoc_calls[0]["safe"]


def test_windows_line_endings_are_read_as_newlines(
    work_dirs: WorkDirs, pandoc_calls: PandocCalls
) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "notes.md").write_bytes(b"a\r\nb\r\n")

    convert_md_to_pdf("notes.md", None, input_dir, output_dir)

    assert pandoc_calls[0]["safe"] == "a\nb\n"


def test_a_windows_1252_file_is_read(work_dirs: WorkDirs, pandoc_calls: PandocCalls) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "notes.md").write_bytes("café\n".encode("cp1252"))

    assert convert_md_to_pdf("notes.md", None, input_dir, output_dir) is True

    assert "café" in pandoc_calls[0]["safe"]


def test_a_utf_16_file_is_reported_and_not_converted(
    work_dirs: WorkDirs, pandoc_calls: PandocCalls, capsys: pytest.CaptureFixture[str]
) -> None:
    input_dir, output_dir = work_dirs
    (input_dir / "notes.md").write_bytes("hi there".encode("utf-16"))

    assert convert_md_to_pdf("notes.md", None, input_dir, output_dir) is False

    assert "UTF-16" in capsys.readouterr().out
    assert pandoc_calls == []


def test_an_overwrite_is_announced(
    work_dirs: WorkDirs, pandoc_calls: PandocCalls, capsys: pytest.CaptureFixture[str]
) -> None:
    input_dir, output_dir = work_dirs
    write_md(input_dir, "notes.md")
    output_dir.mkdir()
    (output_dir / "notes.pdf").write_bytes(b"stale")

    assert convert_md_to_pdf("notes.md", None, input_dir, output_dir) is True

    assert "Overwrote existing file: notes.pdf" in capsys.readouterr().out


def test_a_first_conversion_does_not_claim_an_overwrite(
    work_dirs: WorkDirs, pandoc_calls: PandocCalls, capsys: pytest.CaptureFixture[str]
) -> None:
    input_dir, output_dir = work_dirs
    write_md(input_dir, "notes.md")

    convert_md_to_pdf("notes.md", None, input_dir, output_dir)

    assert "Overwrote" not in capsys.readouterr().out


def test_a_failed_render_is_returned_and_not_announced_as_an_overwrite(
    work_dirs: WorkDirs,
    pandoc_calls: PandocCalls,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_dir, output_dir = work_dirs
    write_md(input_dir, "notes.md")
    output_dir.mkdir()
    (output_dir / "notes.pdf").write_bytes(b"stale")
    monkeypatch.setattr("md_pdf.run_pandoc", lambda *args: False)

    assert convert_md_to_pdf("notes.md", None, input_dir, output_dir) is False

    assert "Overwrote" not in capsys.readouterr().out


def test_an_unexpected_error_is_reported_not_raised(
    work_dirs: WorkDirs,
    pandoc_calls: PandocCalls,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_dir, output_dir = work_dirs
    write_md(input_dir, "notes.md")

    def explode(*args: object) -> bool:
        raise RuntimeError("boom")

    monkeypatch.setattr("md_pdf.run_pandoc", explode)

    assert convert_md_to_pdf("notes.md", None, input_dir, output_dir) is False

    assert "Unexpected error running pandoc: boom" in capsys.readouterr().out
