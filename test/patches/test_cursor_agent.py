"""Tests for patches.cursor_agent."""

from __future__ import annotations

from patches.cursor_agent import (
    BOOT_MARKER,
    MARKER,
    STATUS_INTERVAL_MARKER,
    CursorAgentPatch,
    find_client_config,
)


def test_hot_auth_marker() -> None:
    assert MARKER.startswith("/*") and MARKER.endswith("*/")


def test_status_interval_marker() -> None:
    assert STATUS_INTERVAL_MARKER.startswith("/*") and "status-interval" in STATUS_INTERVAL_MARKER

def test_boot_marker() -> None:
    assert "agentcli-sc-auto-boot" in BOOT_MARKER


def test_metadata_includes_statusline_and_slash() -> None:
    p = CursorAgentPatch()
    assert p.metadata.name == "cursor-agent"
    assert "auto" in p.metadata.tags
    assert "statusline" in p.metadata.tags
    assert "slash" in p.metadata.tags
    assert p.metadata.version >= "2.2.0"


def test_find_client_config() -> None:
    path = find_client_config()
    assert path is not None
    assert path.name == "config.json"
