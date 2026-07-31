"""Tests for sc.status_store compact formatting."""

from __future__ import annotations

from sc.status_store import format_status_lines


def _strip(s: str) -> str:
    out = s
    while "\033[" in out:
        a = out.find("\033[")
        b = out.find("m", a)
        if b < 0:
            break
        out = out[:a] + out[b + 1 :]
    return out


def test_idle_is_single_compact_line() -> None:
    lines = format_status_lines(
        {
            "auto_running": True,
            "action": "ok",
            "email": "alice@example.com",
            "membership": "pro",
            "total_pct": 67.2,
            "auto_pct": 12.0,
            "api_pct": 55.0,
            "plan_status": "OK",
            "poll_n": 12,
        }
    )
    assert len(lines) == 1
    plain = _strip(lines[0])
    assert plain.startswith("SC")
    assert "OK" in plain
    assert "67.2%" in plain
    assert "alice" in plain
    assert "#" in plain or "12" in plain


def test_switching_highlights_event() -> None:
    lines = format_status_lines(
        {
            "action": "switching",
            "email": "old@x.com",
            "total_pct": 96.0,
            "usage_threshold": 95,
            "message": "超阈值，自动换号…",
            "poll_n": 3,
        }
    )
    assert len(lines) == 1
    plain = _strip(lines[0])
    assert "SWITCH" in plain
    assert "96.0%" in plain


def test_polling_shows_refresh_mark() -> None:
    lines = format_status_lines(
        {
            "auto_running": True,
            "action": "polling",
            "email": "a@b.com",
            "total_pct": 40.0,
            "auto_pct": 10.0,
            "api_pct": 30.0,
            "plan_status": "OK",
            "poll_n": 7,
        }
    )
    plain = _strip(lines[0])
    assert "↻" in plain or "#" in plain
    assert "40.0%" in plain
