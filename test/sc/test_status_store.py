"""Tests for sc.status_store formatting."""

from __future__ import annotations

from sc.status_store import format_status_lines


def test_format_status_lines_contains_core_fields() -> None:
    lines = format_status_lines(
        {
            "auto_running": True,
            "auto_pid": 123,
            "action": "polling",
            "message": "#3 total=12.5% 下轮 30s",
            "email": "a@b.com",
            "card": "pro",
            "uid": "auth0|user_ABCDEFGH1234",
            "total_pct": 12.5,
            "auto_pct": 1.0,
            "api_pct": 11.5,
            "poll_n": 3,
            "poll_interval": 30,
            "usage_threshold": 95,
            "keys": 2,
            "updated_iso": "2026-07-31 16:00:00",
        },
        model="Auto",
    )
    assert len(lines) == 3
    joined = "\n".join(lines)
    assert "SC" in joined
    assert "polling" in joined
    assert "a@b.com" in joined
    assert "12.5%" in joined
    assert "#3" in joined
