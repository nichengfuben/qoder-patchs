"""Tests for patches.cursor_agent."""

from __future__ import annotations

from patches.cursor_agent import BOOT_MARKER, MARKER, CursorAgentPatch, find_client_config


def test_hot_auth_marker() -> None:
    assert MARKER.startswith("/*") and MARKER.endswith("*/")


def test_boot_marker() -> None:
    assert "agentcli-sc-auto-boot" in BOOT_MARKER


def test_metadata_no_slash() -> None:
    p = CursorAgentPatch()
    assert p.metadata.name == "cursor-agent"
    assert "slash" not in p.metadata.tags
    assert "auto" in p.metadata.tags


def test_find_client_config() -> None:
    path = find_client_config()
    assert path is not None
    assert path.name == "config.json"
