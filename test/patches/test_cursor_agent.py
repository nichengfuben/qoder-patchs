"""Tests for patches.cursor_agent slash/hot-auth markers."""

from __future__ import annotations

from patches.cursor_agent import (
    MARKER,
    SLASH_MARKER,
    _SLASH_ANCHOR,
    _SLASH_INJECT,
    CursorAgentPatch,
)


def test_slash_inject_contains_marker_and_anchor() -> None:
    assert SLASH_MARKER in _SLASH_INJECT
    assert _SLASH_ANCHOR in _SLASH_INJECT
    assert 'id:"sc"' in _SLASH_INJECT
    assert 'ui.insertText("")}))}),' in _SLASH_INJECT
    assert "ui.insertText('')" not in _SLASH_INJECT or 'ui.insertText("")' in _SLASH_INJECT
    assert 'n("node:child_process")' in _SLASH_INJECT


def test_hot_auth_marker() -> None:
    assert MARKER.startswith("/*") and MARKER.endswith("*/")


def test_metadata() -> None:
    p = CursorAgentPatch()
    assert p.metadata.name == "cursor-agent"
    assert "slash" in p.metadata.tags
