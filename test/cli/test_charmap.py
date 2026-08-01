"""Tests for cli.charmap helpers (echotools-backed)."""

from __future__ import annotations

from cli.echotools_bridge import render_gradient_banner, render_text


class TestRenderText:
    def test_render_text_basic(self):
        lines = render_text("AB")
        assert len(lines) == 6
        assert all(isinstance(line, str) for line in lines)
        assert any("█" in line or "╗" in line for line in lines)

    def test_render_text_single_char(self):
        lines = render_text("A")
        assert len(lines) == 6

    def test_render_text_space(self):
        lines = render_text(" ")
        assert len(lines) == 6

    def test_render_text_lowercase(self):
        lines = render_text("abc")
        assert len(lines) == 6

    def test_render_text_digits(self):
        lines = render_text("012")
        assert len(lines) == 6

    def test_render_text_unknown_char(self):
        lines = render_text("A\u4e2dB")
        assert len(lines) == 6
        lines_ab = render_text("AB")
        assert lines[0] == lines_ab[0]

    def test_render_text_all_unknown(self):
        lines = render_text("\u4e2d\u6587")
        assert len(lines) == 6
        assert all(line == "" for line in lines)

    def test_render_text_empty_string(self):
        lines = render_text("")
        assert len(lines) == 6
        assert all(line == "" for line in lines)


class TestRenderGradientBanner:
    def test_render_gradient_banner(self):
        lines = render_text("HI")
        banner = render_gradient_banner(lines)
        assert isinstance(banner, str)
        assert len(banner) > 0

    def test_render_gradient_banner_custom_palette(self):
        lines = render_text("X")
        custom = [(255, 0, 0), (0, 255, 0)]
        banner = render_gradient_banner(lines, palette=custom)
        assert isinstance(banner, str)

    def test_render_gradient_banner_preserves_line_count(self):
        lines = render_text("OK")
        banner = render_gradient_banner(lines)
        assert banner.count("\n") >= len(lines) - 1
