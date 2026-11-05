"""Tests for platform_tools.py, which finds Chrome, LibreOffice and a monospace font on
macOS, Linux and Windows, and gives install hints for the OS it runs on (#21).
"""

import stat
import sys
from pathlib import Path

import pytest

import platform_tools


def _program(folder: Path, name: str) -> Path:
    path = folder / name
    path.write_text("#!/bin/sh\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


@pytest.fixture
def empty_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """PATH holds only an empty folder, and no fixed install location exists."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.delenv("CHROME_PATH", raising=False)
    monkeypatch.setattr(
        platform_tools, "_CHROME_CANDIDATES",
        tuple(c for c in platform_tools._CHROME_CANDIDATES if "/" not in c and "\\" not in c),
    )
    monkeypatch.setattr(
        platform_tools, "LIBREOFFICE_CANDIDATES",
        tuple(c for c in platform_tools.LIBREOFFICE_CANDIDATES if "/" not in c and "\\" not in c),
    )
    return bin_dir


@pytest.mark.parametrize("name", ["google-chrome", "google-chrome-stable", "chromium",
                                  "chromium-browser"])
def test_chrome_is_found_on_path(empty_path: Path, name: str) -> None:
    program = _program(empty_path, name)

    assert platform_tools.find_chrome() == str(program)


def test_no_chrome_gives_none(empty_path: Path) -> None:
    assert platform_tools.find_chrome() is None


def test_chrome_path_in_the_environment_wins(
    empty_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _program(empty_path, "google-chrome")
    monkeypatch.setenv("CHROME_PATH", "/opt/my/chrome")

    assert platform_tools.find_chrome() == "/opt/my/chrome"


def test_a_chrome_at_a_fixed_path_is_found(
    empty_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _program(tmp_path, "Google Chrome")
    monkeypatch.setattr(platform_tools, "_CHROME_CANDIDATES", (str(app), "google-chrome"))

    assert platform_tools.find_chrome() == str(app)


@pytest.mark.parametrize("name", ["libreoffice", "soffice"])
def test_libreoffice_is_found_on_path(empty_path: Path, name: str) -> None:
    program = _program(empty_path, name)

    assert platform_tools.find_libreoffice_path() == str(program)


def test_no_libreoffice_gives_none(empty_path: Path) -> None:
    assert platform_tools.find_libreoffice_path() is None


def test_menlo_is_picked_when_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        platform_tools, "_installed_font_families", lambda: {"DejaVu Sans Mono", "Menlo"}
    )

    assert platform_tools.mono_font() == "Menlo"


def test_dejavu_is_picked_without_menlo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        platform_tools, "_installed_font_families", lambda: {"DejaVu Sans", "DejaVu Sans Mono"}
    )

    assert platform_tools.mono_font() == "DejaVu Sans Mono"


def test_no_known_mono_font_keeps_the_latex_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(platform_tools, "_installed_font_families", lambda: {"Arial"})

    assert platform_tools.mono_font() is None


def test_without_fc_list_macos_still_gets_menlo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(platform_tools, "_installed_font_families", lambda: None)
    monkeypatch.setattr(sys, "platform", "darwin")

    assert platform_tools.mono_font() == "Menlo"


def test_without_fc_list_elsewhere_keeps_the_latex_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(platform_tools, "_installed_font_families", lambda: None)
    monkeypatch.setattr(sys, "platform", "win32")

    assert platform_tools.mono_font() is None


@pytest.mark.parametrize("platform, expected", [
    ("darwin", "brew install pandoc"),
    ("linux", "sudo apt install pandoc"),
    ("win32", "winget install JohnMacFarlane.Pandoc"),
    ("freebsd14", "sudo apt install pandoc"),
])
def test_install_hints_match_the_os(platform: str, expected: str) -> None:
    assert platform_tools.install_hint("pandoc", platform).startswith(expected)


@pytest.mark.parametrize("platform", ["darwin", "linux", "win32"])
def test_every_tool_has_a_hint_on_every_os(platform: str) -> None:
    for tool in ("tesseract", "pandoc", "latex", "libreoffice", "chrome", "wkhtmltopdf"):
        assert platform_tools.install_hint(tool, platform)
