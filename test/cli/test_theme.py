"""Tests for qoder_patchs.cli.theme module.

Covers BluePalette constants, BLUE_THEME existence, and get_console factory.
"""

from __future__ import annotations

import pytest
from rich.console import Console
from rich.theme import Theme

from qoder_patchs.cli.theme import (
    BLUE_THEME,
    BluePalette,
    get_console,
)


class TestBluePaletteConstants:
    """Test that BluePalette has all expected colour constants."""

    def test_blue_palette_constants(self):
        assert BluePalette.DARK_NAVY == "#0a1628"
        assert BluePalette.NAVY == "#1a2744"
        assert BluePalette.DEEP_BLUE == "#1e3a5f"
        assert BluePalette.BLUE == "#2563eb"
        assert BluePalette.BRIGHT_BLUE == "#3b82f6"
        assert BluePalette.LIGHT_BLUE == "#60a5fa"
        assert BluePalette.SKY == "#93c5fd"
        assert BluePalette.ICE_BLUE == "#bfdbfe"
        assert BluePalette.WHITE_BLUE == "#dbeafe"

    def test_semantic_colors(self):
        assert BluePalette.SUCCESS == "#22c55e"
        assert BluePalette.WARNING == "#eab308"
        assert BluePalette.ERROR == "#ef4444"
        assert BluePalette.INFO == "#06b6d4"
        assert BluePalette.MUTED == "#64748b"

    def test_all_colors_are_hex(self):
        """All palette values should be hex colour strings."""
        import re

        hex_pattern = re.compile(r"^#[0-9a-fA-F]{6}$")
        for attr in dir(BluePalette):
            if attr.isupper():
                value = getattr(BluePalette, attr)
                if isinstance(value, str):
                    assert hex_pattern.match(value), f"{attr} = {value} is not a valid hex color"


class TestBlueThemeExists:
    """Test that BLUE_THEME is a valid Rich Theme."""

    def test_blue_theme_exists(self):
        assert BLUE_THEME is not None
        assert isinstance(BLUE_THEME, Theme)

    def test_blue_theme_has_required_styles(self):
        """Theme should define all expected style keys."""
        expected_keys = [
            "info", "warning", "error", "success",
            "header", "accent", "muted", "border",
        ]
        # Rich Theme stores styles in .styles dict
        for key in expected_keys:
            assert key in BLUE_THEME.styles, f"Missing style key: {key}"


class TestGetConsole:
    """Test the get_console factory function."""

    def test_get_console(self):
        console = get_console(theme=True)
        assert isinstance(console, Console)

    def test_get_console_no_theme(self):
        console = get_console(theme=False)
        assert isinstance(console, Console)

    def test_get_console_returns_new_instance(self):
        c1 = get_console()
        c2 = get_console()
        assert c1 is not c2
