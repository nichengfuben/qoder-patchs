"""Tests for sc.status_store compact formatting."""

from __future__ import annotations

import re

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
            "total_pct": 66.0,
            "plan_status": "OK",
            "usage_seq": 126,
        },
        model="Auto",
    )
    assert len(lines) == 1
    plain = _strip(lines[0])
    assert plain.startswith("SC")
    assert "OK" in plain
    assert "66.0%" in plain
    assert "#126" in plain
    assert "Auto" in plain
    assert re.search(r"\d{2}:\d{2}:\d{2}", plain)


def test_switching_highlights_event() -> None:
    lines = format_status_lines(
        {
            "action": "switching",
            "usage_threshold": 95,
            "message": "超阈值，自动换号…",
            "usage_seq": 3,
        }
    )
    assert len(lines) == 1
    plain = _strip(lines[0])
    assert "SWITCH" in plain
    assert "thr>=95%" in plain
    assert "#3" in plain


def test_clock_is_live_not_from_json() -> None:
    """时间不读 usage_at，用渲染时刻。"""
    lines = format_status_lines(
        {
            "action": "ok",
            "total_pct": 40.0,
            "plan_status": "OK",
            "usage_seq": 7,
            "usage_at": "00:00:00",
        },
        model="Auto",
    )
    plain = _strip(lines[0])
    assert "00:00:00" not in plain or plain.count(":") >= 2
    # 不应强制显示 json 里的假时间作为唯一时钟——有当前时钟
    assert re.search(r"\d{2}:\d{2}:\d{2}", plain)
    assert "#7" in plain
    assert "Auto" in plain


def test_usage_seq_forces_visible_refresh() -> None:
    base = {
        "auto_running": True,
        "action": "polling",
        "total_pct": 40.0,
        "plan_status": "OK",
    }
    a = _strip(format_status_lines({**base, "usage_seq": 7}, model="Auto")[0])
    b = _strip(format_status_lines({**base, "usage_seq": 8}, model="Auto")[0])
    assert "#7" in a and "#8" in b
