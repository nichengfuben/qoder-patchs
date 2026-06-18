"""Tests for qoder_patchs.cli.charmap module.

Covers render_text, unknown character handling, and render_gradient_banner.
"""

from __future__ import annotations

import pytest

from qoder_patchs.cli.charmap import (
    BLUE_GRADIENT_PALETTE,
    CHAR_MAP,
    render_gradient_banner,
    render_text,
)


class TestRenderTextBasic:
    """Test basic ASCII art rendering."""

    def test_render_text_basic(self):
        lines = render_text("AB")
        assert len(lines) == 6  # always 6 lines
        # Each line should be non-empty (A and B both have glyphs)
        for line in lines:
            assert len(line) > 0

    def test_render_text_single_char(self):
        lines = render_text("A")
        assert len(lines) == 6
        # First line of 'A' should contain the glyph
        assert "█" in lines[0] or "╔" in lines[0] or "╗" in lines[0]

    def test_render_text_space(self):
        lines = render_text(" ")
        assert len(lines) == 6
        # Space character should produce minimal-width lines
        for line in lines:
            assert len(line) >= 1

    def test_render_text_lowercase(self):
        lines = render_text("abc")
        assert len(lines) == 6
        # Lowercase glyphs exist in CHAR_MAP
        for line in lines:
            assert len(line) > 0

    def test_render_text_digits(self):
        lines = render_text("012")
        assert len(lines) == 6
        for line in lines:
            assert len(line) > 0


class TestRenderTextUnknownChar:
    """Test handling of characters not in CHAR_MAP."""

    def test_render_text_unknown_char(self):
        """Unknown characters should be silently skipped."""
        lines = render_text("A\u4e2dB")  # \u4e2d = Chinese character '中', not in CHAR_MAP
        assert len(lines) == 6
        # Should still render A and B glyphs
        # The output should be roughly the width of A + B
        lines_ab = render_text("AB")
        for i in range(6):
            assert len(lines[i]) == len(lines_ab[i])

    def test_render_text_all_unknown(self):
        """All unknown characters should produce empty lines."""
        lines = render_text("\u4e2d\u6587")  # Chinese characters
        assert len(lines) == 6
        for line in lines:
            assert line == ""

    def test_render_text_empty_string(self):
        lines = render_text("")
        assert len(lines) == 6
        for line in lines:
            assert line == ""


class TestRenderGradientBanner:
    """Test gradient banner rendering."""

    def test_render_gradient_banner(self):
        lines = render_text("HI")
        banner = render_gradient_banner(lines)
        assert isinstance(banner, str)
        assert len(banner) > 0
        # Should contain newlines (one per line)
        assert "\n" in banner

    def test_render_gradient_banner_custom_palette(self):
        lines = render_text("X")
        custom = [(255, 0, 0), (0, 255, 0)]
        banner = render_gradient_banner(lines, palette=custom)
        assert isinstance(banner, str)

    def test_render_gradient_banner_preserves_line_count(self):
        lines = render_text("OK")
        banner = render_gradient_banner(lines)
        # The banner output should have the same number of lines
        banner_lines = banner.split("\n")
        assert len(banner_lines) == 6


class TestCharmapCompleteness:
    """Test CHAR_MAP data integrity."""

    def test_all_glyphs_are_6_lines(self):
        for ch, glyph in CHAR_MAP.items():
            assert len(glyph) == 6, f"Glyph for {ch!r} has {len(glyph)} lines, expected 6"

    def test_common_chars_present(self):
        for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ":
            assert ch in CHAR_MAP, f"Missing glyph for {ch!r}"

    def test_blue_gradient_palette_has_entries(self):
        assert len(BLUE_GRADIENT_PALETTE) >= 2
        for entry in BLUE_GRADIENT_PALETTE:
            assert len(entry) == 3
            r, g, b = entry
            assert 0 <= r <= 255
            assert 0 <= g <= 255
            assert 0 <= b <= 255
