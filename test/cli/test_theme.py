"""Tests for cli.theme module."""

from __future__ import annotations

from rich.console import Console
from rich.theme import Theme

from cli.commands.theme import (
    DEFAULT_THEME_NAME,
    get_console,
    get_rich_theme,
    list_theme_names,
    normalize_theme_name,
)


class TestThemeRegistry:
    def test_default_theme(self) -> None:
        assert DEFAULT_THEME_NAME == "ocean"

    def test_legacy_blue_alias(self) -> None:
        assert normalize_theme_name("blue") == "ocean"

    def test_theme_diversity(self) -> None:
        names = list_theme_names()
        assert len(names) >= 7
        assert "forest" in names
        assert "sunset" in names

    def test_rich_theme_exists(self) -> None:
        theme = get_rich_theme("forest")
        assert isinstance(theme, Theme)
        assert "header" in theme.styles


class TestGetConsole:
    def test_get_console(self) -> None:
        console = get_console(theme_name="violet")
        assert isinstance(console, Console)

    def test_get_console_unthemed(self) -> None:
        console = get_console(themed=False)
        assert isinstance(console, Console)

    def test_get_console_returns_new_instance(self) -> None:
        assert get_console() is not get_console()
