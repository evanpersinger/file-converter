"""Tests for the Markdown preprocessing in md_pdf.py.

Pandoc is replaced in nearly all of these, because neither it nor xelatex is reachable
from a unit test. What they test is everything that runs before it: the unicode -> LaTeX
maps, the delimiter normalization, and the code-protection that has to survive all of
it. These are the inverse of pdf_md.py's, so the round-trip section checks the pair lines
up. The last section renders real PDFs and is skipped without pandoc, xelatex and macOS.
"""

import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import fitz
import pytest

import md_pdf
from external_tool import ToolTimeout
from md_pdf import (
    _TEXT_DOLLAR,
    LATEX_HEADER,
    PANDOC_FROM,
    PANDOC_FROM_SAFE,
    _combine_adjacent_math,
    _convert_paren_math_to_dollars,
    _convert_underscores_in_math,
    _extract_bad_command,
    _hide_text_dollars,
    _in_math,
    _is_ascii_diagram_line,
    _merge_touching_math,
    _pandoc_once,
    _stash_indented_code,
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
        ("ℝ", r"$\mathbb{R}$"),
        ("ℕ", r"$\mathbb{N}$"),
        ("ℤ", r"$\mathbb{Z}$"),
        ("ℚ", r"$\mathbb{Q}$"),
        ("ℂ", r"$\mathbb{C}$"),
        ("f: ℝ → ℝ", r"f: $\mathbb{R}$ $\rightarrow$ $\mathbb{R}$"),
        ("n ∈ ℕ", r"n $\in$ $\mathbb{N}$"),
        ("⟨", r"$\langle$"),
        ("⟩", r"$\rangle$"),
        ("⟨x, y⟩", r"$\langle$x, y$\rangle$"),
        ("⟨xᵢ, yᵢ⟩", r"$\langle x_{i}$, $y_{i}\rangle$"),
        ("⊕", r"$\oplus$"),
        ("⊗", r"$\otimes$"),
        ("∘", r"$\circ$"),
        ("⊤", r"$\top$"),
        ("V ⊕ W", r"V $\oplus$ W"),
        ("A ⊗ B ⊗ C", r"A $\otimes$ B $\otimes$ C"),
        ("f ∘ g ∘ h", r"f $\circ$ g $\circ$ h"),
        ("≅", r"$\cong$"),
        ("≃", r"$\simeq$"),
        ("G ≅ H", r"G $\cong$ H"),
        ("a ≃ b ≅ c", r"a $\simeq$ b $\cong$ c"),
        ("≪", r"$\ll$"),
        ("≫", r"$\gg$"),
        ("a ≪ b ≫ c", r"a $\ll$ b $\gg$ c"),
        ("′", r"$\prime$"),
        ("″", r"$\dprime$"),
        ("f′(x)", r"f$\prime$(x)"),
        ("f″(x)", r"f$\dprime$(x)"),
        ("⌈", r"$\lceil$"),
        ("⌉", r"$\rceil$"),
        ("⌊", r"$\lfloor$"),
        ("⌋", r"$\rfloor$"),
        ("⌊x⌋", r"$\lfloor$x$\rfloor$"),
        ("⌈x⌉", r"$\lceil$x$\rceil$"),
        ("⌊xᵢ⌋", r"$\lfloor x_{i}\rfloor$"),
        ("⋅", r"$\cdot$"),
        ("∖", r"$\setminus$"),
        ("∣", r"$\mid$"),
        ("∤", r"$\nmid$"),
        ("a ⋅ b ⋅ c", r"a $\cdot$ b $\cdot$ c"),
        ("x ∈ A ∖ B", r"x $\in$ A $\setminus$ B"),
        ("p ∣ n and 3 ∤ 10", r"p $\mid$ n and 3 $\nmid$ 10"),
        ("≢", r"$\nequiv$"),
        ("≺", r"$\prec$"),
        ("≻", r"$\succ$"),
        ("⊢", r"$\vdash$"),
        ("⊨", r"$\models$"),
        ("a ≺ b ≻ c", r"a $\prec$ b $\succ$ c"),
        ("Γ ⊢ A and M ⊨ φ", r"$\Gamma$ $\vdash$ A and M $\models$ $\phi$"),
        ("a ≢ b", r"a $\nequiv$ b"),
        ("⟶", r"$\longrightarrow$"),
        ("⟹", r"$\Longrightarrow$"),
        ("f: A ⟶ B", r"f: A $\longrightarrow$ B"),
        ("a → b ⟶ c ⇒ d ⟹ e", r"a $\rightarrow$ b $\longrightarrow$ c $\Rightarrow$ d $\Longrightarrow$ e"),
        ("𝔼", r"$\mathbb{E}$"),
        ("𝔼[X]", r"$\mathbb{E}$[X]"),
        ("𝔼[X²]", r"$\mathbb{E}$[$X^{2}$]"),
        ("ℙ", r"$\mathbb{P}$"),
        ("ℙ(A)", r"$\mathbb{P}$(A)"),
        ("ℙ(X ≤ x)", r"$\mathbb{P}$(X $≤$ x)"),
        ("ℙ and 𝔼", r"$\mathbb{P}$ and $\mathbb{E}$"),
        ("ϵ", r"$\epsilon$"),
        ("ϕ", r"$\phi$"),
        ("ε and ϵ", r"$\varepsilon$ and $\epsilon$"),
        ("ϕ(x)", r"$\phi$(x)"),
        ("ϵ ~ N(0, σ²)", r"$\epsilon$ ~ N(0, $\sigma^{2}$)"),
        ("ℓ", r"$\ell$"),
        ("ℓ(θ)", r"$\ell$($\theta$)"),
        ("𝒩", r"$\mathcal{N}$"),
        ("𝒩(μ, σ²)", r"$\mathcal{N}$($\mu$, $\sigma^{2}$)"),
        ("X ~ 𝒩(0, 1)", r"X ~ $\mathcal{N}$(0, 1)"),
        ("ε ~ 𝒩(0, σ²)", r"$\varepsilon$ ~ $\mathcal{N}$(0, $\sigma^{2}$)"),
        ("⋯", r"$\cdots$"),
        ("1, 2, ⋯, n", r"1, 2, $\cdots$, n"),
        ("a₁ + a₂ + ⋯ + aₙ", r"$a_{1} + a_{2} + \cdots + a_{n}$"),
        ("x₁ ⋯ xₙ", r"$x_{1}$ $\cdots$ $x_{n}$"),
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
        ("ℝⁿ", r"$\mathbb{R}^{n}$"),
        ("ℝ²", r"$\mathbb{R}^{2}$"),
        ("ℝ₊", r"$\mathbb{R}_{+}$"),
        ("x ∈ ℝⁿ", r"x $\in$ $\mathbb{R}^{n}$"),
        ("ℕ²", r"$\mathbb{N}^{2}$"),
        ("ℤₙ", r"$\mathbb{Z}_{n}$"),
        ("ℚ₊", r"$\mathbb{Q}_{+}$"),
        ("ℂⁿ", r"$\mathbb{C}^{n}$"),
        ("𝔼ₓ[f(x)]", r"$\mathbb{E}_{x}$[f(x)]"),
        ("ℙₓ(A)", r"$\mathbb{P}_{x}$(A)"),
        ("ϵᵢ", r"$\epsilon_{i}$"),
        ("ϕ₁", r"$\phi_{1}$"),
        ("ϵ²", r"$\epsilon^{2}$"),
        ("yᵢ = βxᵢ + ϵᵢ", r"$y_{i} = \beta x_{i} + \epsilon_{i}$"),
        ("ℓ₂ norm", r"$\ell_{2}$ norm"),
        ("ℓ₁ and ℓ₂", r"$\ell_{1}$ and $\ell_{2}$"),
        ("ℓ²", r"$\ell^{2}$"),
        ("𝒩ₚ(μ, Σ)", r"$\mathcal{N}_{p}$($\mu$, $\Sigma$)"),
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
        ("ϵ̂ᵢ", r"$\hat{\epsilon}_{i}$"),
        ("σ̂²", r"$\hat{\sigma}^{2}$"),
        ("β̂²", r"$\hat{\beta}^{2}$"),
        ("β̂₁²", r"$\hat{\beta}_{1}^{2}$"),
        ("α̂ᵢ²", r"$\hat{\alpha}_{i}^{2}$"),
        ("x̂ⁿ", r"$\hat{x}^{n}$"),
        ("σ̂² = 1", r"$\hat{\sigma}^{2}$ = 1"),
        ("ŷ", r"$\hat{y}$"),
        ("ŷᵢ", r"$\hat{y}_{i}$"),
        ("Ŷᵢ", r"$\hat{Y}_{i}$"),
        ("ŷ²", r"$\hat{y}^{2}$"),
        ("eᵢ = yᵢ − ŷᵢ", r"$e_{i} = y_{i}$ − $\hat{y}_{i}$"),
    ],
)
def test_a_hatted_variable_keeps_its_hat_and_subscript(source: str, expected: str) -> None:
    assert convert_symbols(source) == expected


@pytest.mark.parametrize(("source", "expected"), [
    ("$x̂$", r"$\hat{x}$"),
    ("$β̂₁ = 2$", r"$\hat{\beta}_{1} = 2$"),
    ("$ŷᵢ + 1$", r"$\hat{y}_{i} + 1$"),
    ("$$ŷᵢ$$", r"$$\hat{y}_{i}$$"),
])
def test_a_hat_inside_a_math_span_adds_no_delimiters_of_its_own(source: str, expected: str) -> None:
    """The hat pass used to wrap its result in $..$ even inside a span, which turned $x̂$
    into the display delimiter $$\\hat{x}$$ and mangled whatever followed."""
    assert convert_symbols(source) == expected


@pytest.mark.parametrize("source", ["crêpe", "fête", "être", "côte", "âge", "naïve"])
def test_circumflex_letters_in_ordinary_words_are_not_turned_into_hats(source: str) -> None:
    """Only ŷ and Ŷ are read as a letter with a hat, since they never occur in a word."""
    assert convert_symbols(source) == source


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("β̂₁xᵢ", r"$\hat{\beta}_{1}x_{i}$"),
        ("ŷᵢ = β̂₀ + β̂₁xᵢ", r"$\hat{y}_{i} = \hat{\beta}_{0} + \hat{\beta}_{1}x_{i}$"),
        ("(xᵢ − x̄)²", r"($x_{i}$ − $\bar{x})^{2}$"),
        ("∑(yᵢ − ŷᵢ)²", r"$\sum$($y_{i}$ − $\hat{y}_{i})^{2}$"),
        ("(σ̂²)⁻¹", r"($\hat{\sigma}^{2})^{-1}$"),
        ("(xᵢ)²", r"($x_{i})^{2}$"),
    ],
)
def test_a_script_right_after_a_math_span_is_converted(source: str, expected: str) -> None:
    """A letter or ")" touching the closing $ of an earlier span is plain text, so it still
    needs converting. The script pass used to skip anything next to a $, which left the
    unicode script behind and drew it as a blank."""
    result = convert_symbols(source)

    assert result == expected
    assert not [c for c in result if c in md_pdf.SUBSCRIPT_TO_LATEX or c in md_pdf.SUPERSCRIPT_TO_LATEX]


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("$xᵢ$", "$x_{i}$"),
        ("$x² + yᵢ$", "$x^{2} + y_{i}$"),
        ("$(a+b)²$", "$(a+b)^{2}$"),
        ("$$xᵢ$$", "$$x_{i}$$"),
    ],
)
def test_a_script_inside_a_math_span_is_converted_without_new_delimiters(source: str, expected: str) -> None:
    """Wrapping here would turn $xᵢ$ into the display delimiter $$x_{i}$$."""
    assert convert_symbols(source) == expected


@pytest.mark.parametrize(
    "source",
    [
        "(xᵢ − x̄)² and ∑(yᵢ − ŷᵢ)² and (xᵢ)².",
        "x̄ȳ and zᵢ and (aᵢ)²",
        "β̂₁xᵢ and (σ̂²)⁻¹ and yᵢ",
    ],
)
def test_several_script_conversions_on_one_line_each_get_their_own_math(source: str) -> None:
    """Converting ")²" next to an earlier span puts two $ side by side. Counting that as one
    delimiter paired every later $ on the line wrong, so the spans after it came out as
    literal text like y_{i}."""
    result = convert_symbols(source)

    assert "$$" not in result
    # every inline span is a whole $..$ pair: with them removed no $ and no subscript is left
    outside = re.sub(r"\$[^$]+\$", "", result)
    assert "$" not in outside and "_{" not in outside


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("xᵢ²", r"$x_{i}^{2}$"),
        ("xᵢⱼ² and x₁³", r"$x_{ij}^{2}$ and $x_{1}^{3}$"),
        ("θ₀² + θ₁²", r"$\theta_{0}^{2} + \theta_{1}^{2}$"),
        ("ℝ₊ⁿ", r"$\mathbb{R}_{+}^{n}$"),
        ("$xᵢ²$", "$x_{i}^{2}$"),
        ("$$xᵢ²$$", "$$x_{i}^{2}$$"),
    ],
)
def test_a_superscript_after_a_subscript_is_the_same_letters_exponent(source: str, expected: str) -> None:
    """xᵢ² used to come out as $x_{i}$², leaving the ² as a raw unicode character."""
    assert convert_symbols(source) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("∑ᵢ₌₁ⁿ xᵢ", r"$\sum_{i=1}^{n}$ $x_{i}$"),
        ("∑ᵢ₌₁ⁿ xᵢ²", r"$\sum_{i=1}^{n}$ $x_{i}^{2}$"),
        ("∏ᵢ₌₁ⁿ pᵢ", r"$\prod_{i=1}^{n}$ $p_{i}$"),
        ("∫₀¹ f(x) dx", r"$\int_{0}^{1}$ f(x) dx"),
        ("∮₀", r"$\oint_{0}$"),
        ("$∑ᵢ₌₁ⁿ xᵢ$", r"$\sum_{i=1}^{n} x_{i}$"),
    ],
)
def test_the_limits_of_a_sum_product_or_integral_become_its_scripts(source: str, expected: str) -> None:
    """The big operators were not a base the script pass recognised, so ∑ᵢ₌₁ⁿ left its
    limits as raw unicode and they drew blank."""
    assert convert_symbols(source) == expected


def test_a_big_operator_without_limits_is_unchanged() -> None:
    assert convert_symbols("∑ x and a∑b") == r"$\sum$ x and a$\sum$b"


def test_a_script_after_a_price_is_still_converted() -> None:
    """A text dollar is not a math delimiter, so it must not count as being inside math."""
    assert convert_symbols(r"costs \$5 and xᵢ") == r"costs \$5 and $x_{i}$"


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
        (r"\epsilon_i", r"$\epsilon_i$"),
        (r"\epsilon in prose", r"$\epsilon$ in prose"),
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


@pytest.mark.parametrize("source", ["$α + β$ here", "$$Σ x$$", "$x$ and $α$", "$x ∈ ℝ$", "$n ∈ ℕ$", "$⟨x, y⟩$", "$V ⊕ W$", "$G ≅ H$", "$f′(x) ≪ 1$", "$⌊x⌋$", "$a ⋅ b$", "$Γ ⊢ A$", "$A ⟹ B$", "$𝔼[X]$", "$ℙ(A)$", "$ϵ + ϕ$", "$ℓ(θ)$", "$𝒩(0, 1)$", "$a + ⋯ + b$"])
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


@pytest.mark.parametrize("source", ["a ⨁ b", "ℵ"])
def test_unmapped_symbols_pass_through_untouched(source: str) -> None:
    """Nothing in the maps matches these, so they stay as typed. The text font has no
    glyph for them, so they draw blank until someone maps them."""
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


# Naming the command xelatex choked on

UNDEFINED_COMMAND_ERROR = "! Undefined control sequence.\nl.12 Here $\\foo\n                {x}$ is odd.\n"


@pytest.mark.parametrize(("error", "expected"), [
    (UNDEFINED_COMMAND_ERROR, "\\foo"),
    ("! Undefined control sequence.\nl.3 \\alpha and \\bar\n", "\\bar"),
    ("! Undefined control sequence.\nl.7 plain words only\n", None),
    ("! Missing $ inserted.\nl.185 \\frac{1}{n}", None),
    ("", None),
])
def test_the_command_xelatex_stopped_on_is_named(error: str, expected: str | None) -> None:
    """The last command on the error's source line is the one TeX stopped at, and any other
    kind of error names none."""
    assert _extract_bad_command(error) == expected


# run_pandoc, with each pandoc run scripted

ScriptedPandoc = Callable[..., PandocCalls]


@pytest.fixture
def scripted_pandoc(monkeypatch: pytest.MonkeyPatch) -> ScriptedPandoc:
    """Replace _pandoc_once with one that returns each (ok, error) given, in turn, and
    records what it was handed. No mermaid filter is found unless a test says so."""

    def install(*results: tuple[bool, str]) -> PandocCalls:
        calls: PandocCalls = []
        remaining = list(results)

        def fake(md_text: str, output_path: Path, from_fmt: str, header_path: str, mermaid_filter: str | None):
            calls.append({
                "text": md_text,
                "output": output_path,
                "from": from_fmt,
                "header": Path(header_path),
                "header_text": Path(header_path).read_text(encoding="utf-8"),
                "mermaid": mermaid_filter,
            })
            return remaining.pop(0)

        monkeypatch.setattr("md_pdf._pandoc_once", fake)
        monkeypatch.setattr("md_pdf.which", lambda name: None)
        return calls

    return install


def test_a_good_full_render_is_the_only_render(
    scripted_pandoc: ScriptedPandoc, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    calls = scripted_pandoc((True, ""))

    assert run_pandoc("RICH", "SAFE", tmp_path / "out.pdf", "notes.md") is True

    assert len(calls) == 1
    assert calls[0]["text"] == "RICH" and calls[0]["from"] == PANDOC_FROM
    assert "Converted notes.md to out.pdf" in capsys.readouterr().out


def test_a_failed_full_render_retries_the_safe_text_with_math_off(
    scripted_pandoc: ScriptedPandoc, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    calls = scripted_pandoc((False, UNDEFINED_COMMAND_ERROR), (True, ""))

    assert run_pandoc("RICH", "SAFE", tmp_path / "out.pdf", "notes.md") is True

    assert [call["text"] for call in calls] == ["RICH", "SAFE"]
    assert [call["from"] for call in calls] == [PANDOC_FROM, PANDOC_FROM_SAFE]
    out = capsys.readouterr().out
    assert "undefined LaTeX command '\\foo'" in out
    assert "safe mode (math shown as text): notes.md to out.pdf" in out


def test_an_error_that_names_no_command_still_retries_in_safe_mode(
    scripted_pandoc: ScriptedPandoc, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    scripted_pandoc((False, "! Missing $ inserted."), (True, ""))

    assert run_pandoc("RICH", "SAFE", tmp_path / "out.pdf", "notes.md") is True

    out = capsys.readouterr().out
    assert "full render failed; retrying in safe mode" in out
    assert "undefined LaTeX command" not in out


def test_when_both_renders_fail_the_safe_error_is_reported(
    scripted_pandoc: ScriptedPandoc, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    scripted_pandoc((False, "first error"), (False, "second error"))

    assert run_pandoc("RICH", "SAFE", tmp_path / "out.pdf", "notes.md") is False

    assert "pandoc failed: second error" in capsys.readouterr().out


def test_both_renders_get_the_latex_header_and_it_is_removed_afterwards(
    scripted_pandoc: ScriptedPandoc, tmp_path: Path
) -> None:
    calls = scripted_pandoc((False, "x"), (True, ""))

    run_pandoc("RICH", "SAFE", tmp_path / "out.pdf", "notes.md")

    assert calls[0]["header_text"] == calls[1]["header_text"] == LATEX_HEADER
    assert calls[0]["header"] == calls[1]["header"]
    assert not calls[0]["header"].exists()


def test_the_header_is_removed_when_both_renders_fail(
    scripted_pandoc: ScriptedPandoc, tmp_path: Path
) -> None:
    calls = scripted_pandoc((False, "x"), (False, "y"))

    run_pandoc("RICH", "SAFE", tmp_path / "out.pdf", "notes.md")

    assert not calls[0]["header"].exists()


def test_the_header_is_removed_when_a_render_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    headers: list[Path] = []

    def explode(md_text: str, output_path: Path, from_fmt: str, header_path: str, mermaid_filter: str | None):
        headers.append(Path(header_path))
        raise RuntimeError("boom")

    monkeypatch.setattr("md_pdf._pandoc_once", explode)
    monkeypatch.setattr("md_pdf.which", lambda name: None)

    with pytest.raises(RuntimeError, match="boom"):
        run_pandoc("RICH", "SAFE", tmp_path / "out.pdf", "notes.md")

    assert not headers[0].exists()


def test_an_installed_mermaid_filter_is_passed_to_both_renders(
    scripted_pandoc: ScriptedPandoc, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = scripted_pandoc((False, "x"), (True, ""))
    monkeypatch.setattr("md_pdf.which", lambda name: "/bin/mermaid-filter" if name == "mermaid-filter" else None)

    run_pandoc("RICH", "SAFE", tmp_path / "out.pdf", "notes.md")

    assert [call["mermaid"] for call in calls] == ["/bin/mermaid-filter", "/bin/mermaid-filter"]


def test_no_mermaid_filter_is_passed_when_none_is_installed(
    scripted_pandoc: ScriptedPandoc, tmp_path: Path
) -> None:
    calls = scripted_pandoc((True, ""))

    run_pandoc("RICH", "SAFE", tmp_path / "out.pdf", "notes.md")

    assert calls[0]["mermaid"] is None


# One pandoc run, with the tool replaced


def fake_tool(
    monkeypatch: pytest.MonkeyPatch,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
    create: Path | None = None,
) -> dict[str, object]:
    """Replace run_tool. `create` is a file the fake "pandoc" writes, like the PDF."""
    seen: dict[str, object] = {}

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        seen["command"] = command
        seen["env"] = kwargs.get("env")
        seen["input"] = Path(command[1]).read_text(encoding="utf-8")
        if create is not None:
            create.write_bytes(b"%PDF")
        return subprocess.CompletedProcess(command, returncode, stdout, stderr)

    monkeypatch.setattr("md_pdf.run_tool", run)
    return seen


def test_a_successful_run_asks_pandoc_for_a_pdf_through_xelatex(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = tmp_path / "out.pdf"
    seen = fake_tool(monkeypatch, create=out)

    result = _pandoc_once("# hi", out, PANDOC_FROM, str(tmp_path / "h.tex"), None)

    assert result == (True, "")
    command = seen["command"]
    assert command[0] == "pandoc"
    assert command[2:4] == ["-o", str(out)]
    for flag in ("--pdf-engine=xelatex", "--standalone", f"--from={PANDOC_FROM}", "--to=pdf"):
        assert flag in command
    assert f"--include-in-header={tmp_path / 'h.tex'}" in command
    assert "--filter" not in command


def test_pandoc_reads_the_text_it_was_given(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seen = fake_tool(monkeypatch, create=tmp_path / "out.pdf")

    _pandoc_once("# hi\n\n$x$", tmp_path / "out.pdf", PANDOC_FROM, "h.tex", None)

    assert seen["input"] == "# hi\n\n$x$"


def test_a_mermaid_filter_is_added_to_the_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seen = fake_tool(monkeypatch, create=tmp_path / "out.pdf")

    _pandoc_once("# hi", tmp_path / "out.pdf", PANDOC_FROM, "h.tex", "/bin/mermaid-filter")

    assert seen["command"][-2:] == ["--filter", "/bin/mermaid-filter"]


def test_xelatex_is_told_to_refuse_absolute_and_parent_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """openin_any=p stops a \\input{/some/file} in the markdown pulling a local file in."""
    seen = fake_tool(monkeypatch, create=tmp_path / "out.pdf")

    _pandoc_once("# hi", tmp_path / "out.pdf", PANDOC_FROM, "h.tex", None)

    assert seen["env"]["openin_any"] == "p"


def test_the_temp_markdown_file_is_removed_after_the_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen = fake_tool(monkeypatch, create=tmp_path / "out.pdf")

    _pandoc_once("# hi", tmp_path / "out.pdf", PANDOC_FROM, "h.tex", None)

    assert not Path(seen["command"][1]).exists()


def test_the_temp_markdown_file_is_removed_when_the_tool_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    temp_files: list[Path] = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        temp_files.append(Path(command[1]))
        raise ToolTimeout("pandoc took longer than 300 seconds")

    monkeypatch.setattr("md_pdf.run_tool", run)

    with pytest.raises(ToolTimeout):
        _pandoc_once("# hi", tmp_path / "out.pdf", PANDOC_FROM, "h.tex", None)

    assert not temp_files[0].exists()


def test_a_failed_run_returns_pandoc_stderr(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_tool(monkeypatch, returncode=1, stderr="  boom  \n")

    assert _pandoc_once("# hi", tmp_path / "out.pdf", PANDOC_FROM, "h.tex", None) == (False, "boom")


def test_a_failed_run_also_returns_pandoc_stdout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_tool(monkeypatch, returncode=1, stdout="extra\n", stderr="boom")

    result = _pandoc_once("# hi", tmp_path / "out.pdf", PANDOC_FROM, "h.tex", None)

    assert result == (False, "boom\nstdout: extra")


def test_a_failed_run_with_no_message_says_unknown_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_tool(monkeypatch, returncode=1)

    assert _pandoc_once("# hi", tmp_path / "out.pdf", PANDOC_FROM, "h.tex", None) == (False, "unknown error")


def test_a_clean_exit_that_wrote_no_pdf_is_a_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_tool(monkeypatch, returncode=0)

    assert _pandoc_once("# hi", tmp_path / "out.pdf", PANDOC_FROM, "h.tex", None) == (False, "unknown error")


def test_the_error_file_mermaid_filter_leaves_behind_is_removed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out.pdf"

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        out.write_bytes(b"%PDF")
        (tmp_path / "mermaid-filter.err").write_text("oops", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("md_pdf.run_tool", run)

    _pandoc_once("# hi", out, PANDOC_FROM, "h.tex", "/bin/mermaid-filter")

    assert not (tmp_path / "mermaid-filter.err").exists()


# Real PDFs, through real pandoc and xelatex

needs_latex = pytest.mark.skipif(
    sys.platform != "darwin" or not (shutil.which("pandoc") and shutil.which("xelatex")),
    reason="needs pandoc, xelatex and macOS (the header asks for the Menlo font)",
)

# What xelatex draws in place of a character the font has no glyph for
MISSING_GLYPH = "\uffff"


def render(work_dirs: WorkDirs, capsys: pytest.CaptureFixture[str], markdown: str) -> tuple[str, str]:
    """Convert markdown with the real converter and return (what it printed, the PDF's text)."""
    input_dir, output_dir = work_dirs
    (input_dir / "doc.md").write_text(markdown, encoding="utf-8")
    converted = convert_md_to_pdf("doc.md", None, input_dir, output_dir)
    log = capsys.readouterr().out
    assert converted, log
    with fitz.open(output_dir / "doc.pdf") as document:
        return log, "\n".join(page.get_text() for page in document)


@needs_latex
def test_well_formed_math_renders_in_full(work_dirs: WorkDirs, capsys: pytest.CaptureFixture[str]) -> None:
    log, text = render(work_dirs, capsys, "The estimator $\\hat{\\beta}$ is $\\alpha \\le \\beta$.\n")

    assert "safe mode" not in log
    assert "$" not in text
    assert "≤" in text


@needs_latex
def test_unicode_math_and_the_same_math_in_latex_render_alike(
    work_dirs: WorkDirs, capsys: pytest.CaptureFixture[str]
) -> None:
    _, from_unicode = render(work_dirs, capsys, "α ≤ β and ∑ x²\n")
    _, from_latex = render(work_dirs, capsys, "$\\alpha \\le \\beta$ and $\\sum x^2$\n")

    assert from_unicode == from_latex


@needs_latex
def test_the_transpose_and_therefore_signs_are_drawn(
    work_dirs: WorkDirs, capsys: pytest.CaptureFixture[str]
) -> None:
    _, text = render(work_dirs, capsys, "Qᵀ and ∴ done\n")

    assert "∴" in text and "𝑇" in text
    assert MISSING_GLYPH not in text


@needs_latex
def test_every_mapped_symbol_is_drawn(work_dirs: WorkDirs, capsys: pytest.CaptureFixture[str]) -> None:
    log, text = render(work_dirs, capsys, "a α b ∑ c ∫ d ∞ e → f ⇒ g ≤ h ≥ i ± j ≈ k × l ≠ m ∈ n ℝ o ℝⁿ p ℝ₊ q ℕ r ℤ s ℚ t ℂⁿ u ⟨x, y⟩ v ⊕ w ⊗ x ∘ y ⊤ z ≅ a ≃ b c ≪ d ≫ e f′ g″ h ⌊x⌋ i ⌈y⌉ j a ⋅ b k A ∖ B l p ∣ n m 3 ∤ 10 n ≢ o ≺ p ≻ q ⊢ r ⊨ s ⟶ t ⟹ u v 𝔼[X] w 𝔼ₓ[f(x)] x Var(X) = 𝔼[X²] − 𝔼[X]² y ℙ(A | B) = ℙ(A ∩ B) / ℙ(B) z yᵢ = βxᵢ + ϵᵢ and ϕ₁ and ϵ̂ᵢ and ℓ₂ norm and ℓ(θ) and ε ~ 𝒩(0, σ²) and 𝒩ₚ(μ, Σ) and a₁ + a₂ + ⋯ + aₙ and 1, 2, ⋯, n and σ̂² and β̂₁² and α̂ᵢ and eᵢ = yᵢ − ŷᵢ and $β̂₁ = 2$\n")

    assert "safe mode" not in log, "a mapped command does not exist, so the whole file fell back"
    assert MISSING_GLYPH not in text


@needs_latex
def test_scripts_next_to_a_math_span_are_drawn(work_dirs: WorkDirs, capsys: pytest.CaptureFixture[str]) -> None:
    log, text = render(
        work_dirs,
        capsys,
        "ŷᵢ = β̂₀ + β̂₁xᵢ and (xᵢ − x̄)² and ∑(yᵢ − ŷᵢ)² and (σ̂²)⁻¹ and (xᵢ)² and $xᵢ$ "
        "and xᵢ² and ∑ᵢ₌₁ⁿ xᵢ² and ∏ᵢ₌₁ⁿ pᵢ and ∫₀¹ f(x) dx and ℝ₊ⁿ\n",
    )

    assert "safe mode" not in log
    assert MISSING_GLYPH not in text and "\x00" not in text
    # a span pandoc did not take as math prints its source, like y_{i}
    assert "_{" not in text and "^{" not in text


@needs_latex
def test_an_unknown_command_sends_the_file_to_safe_mode_with_its_math_as_text(
    work_dirs: WorkDirs, capsys: pytest.CaptureFixture[str]
) -> None:
    log, text = render(work_dirs, capsys, "Here $\\foo{x}$ is odd.\n")

    assert "safe mode" in log
    assert "\\foo" in text


@needs_latex
def test_a_span_with_a_space_after_the_opening_dollar_sends_the_file_to_safe_mode(
    work_dirs: WorkDirs, capsys: pytest.CaptureFixture[str]
) -> None:
    """The line from anova-proofs.md that failed: pandoc does not read "$ A" as math, so its
    \\frac lands outside math and xelatex stops."""
    line = (
        "$$ SSR = \\sum (\\hat{Y}_i - \\bar{Y})^2 $$ where $ A = \\frac{1}{n} "
        "\\begin{pmatrix} 1 & \\cdots & 1 \\end{pmatrix} \\rightarrow 1/n $$\n"
    )

    log, _ = render(work_dirs, capsys, line)

    assert "safe mode" in log


@needs_latex
def test_display_math_with_a_blank_line_inside_is_printed_raw(
    work_dirs: WorkDirs, capsys: pytest.CaptureFixture[str]
) -> None:
    """The md-best-practices skill tells Claude never to leave a blank line inside $$. If
    this starts rendering as math, update the skill."""
    _, text = render(work_dirs, capsys, "$$\na = b\n\nc = d\n$$\n")

    assert "$$" in text


@needs_latex
def test_a_space_after_an_opening_dollar_is_printed_raw(
    work_dirs: WorkDirs, capsys: pytest.CaptureFixture[str]
) -> None:
    """Also in the md-best-practices skill, for spans the trimming rules do not reach."""
    _, text = render(work_dirs, capsys, "Here $ x + y$ is math.\n")

    assert "$ x + y$" in text


@needs_latex
def test_an_escaped_price_and_a_dollar_in_code_survive(
    work_dirs: WorkDirs, capsys: pytest.CaptureFixture[str]
) -> None:
    log, text = render(work_dirs, capsys, "It costs \\$5 and `$HOME` stays.\n")

    assert "safe mode" not in log
    assert "It costs $5 and $HOME stays." in text


@needs_latex
def test_math_only_bullets_come_out_as_separate_bullets(
    work_dirs: WorkDirs, capsys: pytest.CaptureFixture[str]
) -> None:
    _, text = render(work_dirs, capsys, "Formulas\n\n- $a = 1$\n\n- $b = 2$\n\n- $c = 3$\n")

    assert text.count("•") == 3


@needs_latex
def test_a_table_cell_keeps_its_math_and_its_negative_number(
    work_dirs: WorkDirs, capsys: pytest.CaptureFixture[str]
) -> None:
    log, text = render(work_dirs, capsys, "| x | y |\n|---|---|\n| $\\alpha$ | -5 |\n")

    assert "safe mode" not in log
    assert "𝛼" in text and "-5" in text


@needs_latex
def test_a_narrow_header_row_is_drawn_as_a_title_above_the_table(
    work_dirs: WorkDirs, capsys: pytest.CaptureFixture[str]
) -> None:
    log, text = render(work_dirs, capsys, "| Title |\n| a | b | c | d |\n|---|---|---|---|\n| 1 | 2 | 3 | 4 |\n")

    assert "safe mode" not in log
    assert text.startswith("Title")


@needs_latex
def test_a_tag_in_backticks_is_drawn_and_a_dash_is_flattened(
    work_dirs: WorkDirs, capsys: pytest.CaptureFixture[str]
) -> None:
    _, text = render(work_dirs, capsys, "Use the `<tag>` here, one \u2014 two.\n")

    assert "<tag>" in text
    assert "one - two" in text


@needs_latex
def test_the_example_in_the_md_best_practices_skill_renders_in_full(
    work_dirs: WorkDirs, capsys: pytest.CaptureFixture[str]
) -> None:
    """Keeps the skill's example honest: if it stops rendering, the skill is teaching a
    pattern that no longer works."""
    example = (
        "The Gauss-Markov theorem says $\\hat{\\beta}$ is the BLUE (Best Linear Unbiased Estimator).\n\n"
        "Since $\\hat{\\beta}$ is unbiased, $E(\\hat{\\beta}) = C \\cdot X\\beta = \\beta$, "
        "so $CX = I_{p \\times p}$.\n\n"
        "$$\n\\begin{aligned}\n\\text{Var}(\\hat{\\beta}) &= \\sigma^2 C C^T \\\\\n"
        "&\\ge \\text{Var}(\\hat{\\beta})\n\\end{aligned}\n$$\n"
    )

    log, text = render(work_dirs, capsys, example)

    assert "safe mode" not in log
    assert "$" not in text and MISSING_GLYPH not in text
    assert "Var" in text


# The $-handling helpers, directly

T = _TEXT_DOLLAR


@pytest.mark.parametrize(("source", "expected"), [
    ("", ""),
    ("$", T),
    ("a$", f"a{T}"),
    ("$a", f"{T}a"),
    ("$$a", f"{T}{T}a"),
    ("a $$ b", f"a {T}{T} b"),
    ("$a$", "$a$"),
    ("$$a$$", "$$a$$"),
    ("$ a $", f"{T} a {T}"),
    ("\\$", T),
    ("\\\\$a$", "\\\\$a$"),
    ("$a\\$b$", "$a\\$b$"),
    ("$a$5", f"{T}a{T}5"),
    ("$x$ and $5", f"$x$ and {T}5"),
    ("$5-$10", f"{T}5-{T}10"),
    ("$a\n\nb$", f"{T}a\n\nb{T}"),
    ("$$\n\n$$", f"{T}{T}\n\n{T}{T}"),
])
def test_only_a_dollar_pandoc_reads_as_text_is_hidden(source: str, expected: str) -> None:
    """An opener needs a non-space after it, a closer a non-space before it and no digit
    after it, math never crosses a blank line, and an escaped dollar is never a delimiter."""
    assert _hide_text_dollars(source) == expected


def stash_blocks(source: str) -> tuple[str, list[str]]:
    stashed: list[str] = []

    def stash(block: str) -> str:
        stashed.append(block)
        return f"<S{len(stashed) - 1}>"

    return _stash_indented_code(source, stash), stashed


@pytest.mark.parametrize(("source", "expected", "blocks"), [
    ("", "", []),
    ("plain", "plain", []),
    ("    code", "<S0>", ["    code"]),
    ("\tcode", "<S0>", ["\tcode"]),
    ("text\n\n    code", "text\n\n<S0>", ["    code"]),
    ("    code\ntext", "<S0>\ntext", ["    code"]),
    ("text\n\n    code\n    more\n\ntail", "text\n\n<S0>\n\ntail", ["    code\n    more"]),
    ("a\n\n    one\n\n    two\n\nb", "a\n\n<S0>\n\nb", ["    one\n\n    two"]),
    ("    code\n\n\ntail", "<S0>\n\n\ntail", ["    code"]),
])
def test_an_indented_block_is_stashed_whole_without_its_trailing_blank_lines(
    source: str, expected: str, blocks: list[str]
) -> None:
    assert stash_blocks(source) == (expected, blocks)


def test_an_indented_line_straight_after_a_paragraph_is_not_code() -> None:
    """Markdown lets a paragraph continue onto an indented line, and indented code cannot
    interrupt a paragraph."""
    assert stash_blocks("text\n    more text") == ("text\n    more text", [])


@pytest.mark.parametrize(("text", "pos", "expected"), [
    ("", 0, False),
    ("$a$ b", 1, True),
    ("$a$ b", 4, False),
    ("a $b$ c $d$", 4, True),
    ("a $b$ c $d$", 7, False),
    ("a $b$ c $d$", 10, True),
    ("$$x$$ y", 3, True),
    ("$$x$$ y", 6, False),
])
def test_a_position_is_in_math_when_an_odd_number_of_delimiters_precede_it(
    text: str, pos: int, expected: bool
) -> None:
    assert _in_math(text, pos) is expected


@pytest.mark.parametrize(("source", "expected"), [
    ("$a$$b$", "$a b$"),
    ("$a$$b$$c$", "$a b c$"),
    ("a$b$$c$d", "a$b c$d"),
    ("$$x$$ and $a$$b$", "$$x$$ and $a b$"),
    ("$$x$$", "$$x$$"),
    ("$a$ $b$", "$a$ $b$"),
])
def test_touching_spans_merge_but_display_math_and_spaced_spans_do_not(source: str, expected: str) -> None:
    assert _merge_touching_math(source) == expected


@pytest.mark.parametrize(("source", "expected"), [
    ("x_12", "x_{12}"),
    ("k_1x", "k_{1}x"),
    ("x_ij", "x_{ij}"),
    ("α_i", r"\alpha_i"),
    ("x_1", "x_1"),
    ("x_{ab}", "x_{ab}"),
    (r"\beta_1", r"\beta_1"),
    (r"a\_b", r"a\_b"),
    ("|a_b|", "|a_b|"),
])
def test_underscore_subscripts_in_math_are_grouped_when_they_need_to_be(source: str, expected: str) -> None:
    """A multi-letter or multi-digit subscript needs braces, a lone one does not, an
    escaped underscore is literal, and a table separator's pipe is not a variable."""
    assert _convert_underscores_in_math(source) == expected


@pytest.mark.parametrize(("source", "expected"), [
    ("$a$ = $b$ = $c$", "$a = b = c$"),
    ("$a$ - $b$ - $c$", "$a - b - c$"),
    ("$a$+$b$", "$a + b$"),
    ("$a$ +  $b$", "$a + b$"),
    ("$a$ * $b$", "$a$ * $b$"),
])
def test_a_chain_of_spans_joined_by_operators_becomes_one_span(source: str, expected: str) -> None:
    assert _combine_adjacent_math(source) == expected


# Things that must hold for any input


CONVERT_SYMBOLS_SAMPLES = [
    "α ≤ β and ∑ x²",
    "θ₀ + β̂₁",
    "√(σ²) and √2",
    "cost $5 and α",
    "$a$ + α",
    "x̄ = 0",
    "∑xᵢ",
    "Qᵀ ∴ x",
    "$$\nα\n$$",
    "`α` and α",
    "- $a$\n\n- $b$",
    "\\beta_1 and \\hat\\beta",
    "t_{0.975,10}",
    "~~~\nPRICE=$5\n~~~",
    "Run:\n\n    echo $HOME\n\nDone.",
]


@pytest.mark.parametrize("source", CONVERT_SYMBOLS_SAMPLES)
def test_converting_symbols_twice_changes_nothing(source: str) -> None:
    """The output is already in the form every pass is looking for, so running the pass
    again must not wrap, escape or merge anything a second time."""
    once = convert_symbols(source)

    assert convert_symbols(once) == once


@pytest.mark.parametrize("source", [
    "",
    "$",
    "$$",
    "$" * 50,
    "\\",
    "\\\\\\",
    "\x00",
    "$\x00$",
    "√",
    "√(",
    "√((",
    "̂",
    "x̂",
    "```",
    "`",
    "∑" * 200,
    "a" * 5000,
])
def test_odd_input_never_raises_in_the_symbol_pass(source: str) -> None:
    assert isinstance(convert_symbols(source), str)


# The command line


@pytest.fixture
def cli_calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str | None]]:
    """Replace the conversion with one that records its arguments and fails for any file
    whose name starts with "bad"."""
    calls: list[tuple[str, str | None]] = []

    def fake_convert(md_path: str, output_path: str | None = None, *rest: object) -> bool:
        calls.append((md_path, output_path))
        return not md_path.startswith("bad")

    monkeypatch.setattr("md_pdf.convert_md_to_pdf", fake_convert)
    return calls


def test_with_no_arguments_and_no_files_it_says_how_to_use_it(
    cli_calls: list[tuple[str, str | None]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["md_pdf.py"])
    monkeypatch.setattr("md_pdf.INPUT_DIR", tmp_path)

    md_pdf.main()

    out = capsys.readouterr().out
    assert "No .md files found in input folder" in out and "Usage: python md_pdf.py" in out
    assert cli_calls == []


def test_with_no_arguments_it_converts_every_markdown_file_in_the_input_folder(
    cli_calls: list[tuple[str, str | None]], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for name in ("a.md", "B.MD", "notes.txt"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["md_pdf.py"])
    monkeypatch.setattr("md_pdf.INPUT_DIR", tmp_path)

    md_pdf.main()

    assert sorted(cli_calls) == [("B.MD", None), ("a.md", None)]


def test_one_failure_in_the_batch_still_converts_the_rest_and_exits_nonzero(
    cli_calls: list[tuple[str, str | None]], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for name in ("bad.md", "good.md"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["md_pdf.py"])
    monkeypatch.setattr("md_pdf.INPUT_DIR", tmp_path)

    with pytest.raises(SystemExit) as exit_info:
        md_pdf.main()

    assert exit_info.value.code == 1
    assert {name for name, _ in cli_calls} == {"bad.md", "good.md"}


@pytest.mark.parametrize(("argv", "expected"), [
    (["md_pdf.py", "notes.md"], [("notes.md", None)]),
    (["md_pdf.py", "notes.md", "out.pdf"], [("notes.md", "out.pdf")]),
])
def test_a_named_file_is_converted_with_the_output_name_if_one_is_given(
    cli_calls: list[tuple[str, str | None]],
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
    expected: list[tuple[str, str | None]],
) -> None:
    monkeypatch.setattr(sys, "argv", argv)

    md_pdf.main()

    assert cli_calls == expected


def test_a_named_file_that_fails_exits_nonzero(
    cli_calls: list[tuple[str, str | None]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", ["md_pdf.py", "bad.md"])

    with pytest.raises(SystemExit) as exit_info:
        md_pdf.main()

    assert exit_info.value.code == 1
