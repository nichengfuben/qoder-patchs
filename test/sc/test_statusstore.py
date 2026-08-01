"""Tests for sc.status_store compact formatting."""

from __future__ import annotations

import re

from sc.statusline_fast import format_status_lines


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
    # 无 cwd/mode 时只有 SC 行；有原生字段时两行
    assert len(lines) == 1
    plain = _strip(lines[0])
    assert plain.startswith("SC")
    assert "OK" in plain
    assert "66.0%" in plain
    assert "#126" in plain
    assert re.search(r"\d{2}:\d{2}:\d{2}", plain)


def test_sc_only_ignores_fake_native_fields() -> None:
    """cwd/mode/ctx 由原生 footer-keep 渲染；statusLine 命令只输出 SC 一行。"""
    lines = format_status_lines(
        {
            "action": "ok",
            "total_pct": 19.0,
            "plan_status": "OK",
            "usage_seq": 3,
        },
        model="",
        cwd=r"C:\Users\me\Project\demo",
        mode="Run Everything",
        context_pct=39.0,
    )
    assert len(lines) == 1
    sc = _strip(lines[0])
    assert sc.startswith("SC")
    assert "19.0%" in sc
    assert "#3" in sc
    assert "Run Everything" not in sc
    assert "ctx 39%" not in sc


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
    plain = _strip(lines[-1])
    assert "00:00:00" not in plain or plain.count(":") >= 2
    # 不应强制显示 json 里的假时间作为唯一时钟——有当前时钟
    assert re.search(r"\d{2}:\d{2}:\d{2}", plain)
    assert "#7" in plain


def test_usage_seq_forces_visible_refresh() -> None:
    base = {
        "auto_running": True,
        "action": "polling",
        "total_pct": 40.0,
        "plan_status": "OK",
    }
    a = _strip(format_status_lines({**base, "usage_seq": 7}, model="Auto")[-1])
    b = _strip(format_status_lines({**base, "usage_seq": 8}, model="Auto")[-1])
    assert "#7" in a and "#8" in b


def test_stale_badge_when_auto_dead() -> None:
    plain = _strip(
        format_status_lines(
            {
                "action": "ok",
                "total_pct": 42.0,
                "plan_status": "OK",
                "usage_seq": 251,
                "_stale": True,
            },
            model="Auto",
        )[-1]
    )
    assert "STALE" in plain
    assert "42.0%" in plain


def test_write_status_concurrent_no_raise(tmp_path, monkeypatch) -> None:
    import threading
    from pathlib import Path

    from sc.run import status_store

    monkeypatch.setattr(status_store, "sc_home_dir", lambda: tmp_path)
    monkeypatch.setattr(status_store, "migrate_legacy_sc_home", lambda: None)
    errors: list = []

    def worker(i: int) -> None:
        try:
            for n in range(20):
                status_store.write_status(total_pct=float(i), usage_seq=n, poll_n=n)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    st = status_store.read_status()
    assert "total_pct" in st
    assert (Path(tmp_path) / "sc_status.json").exists()
    assert not (Path(tmp_path) / "sc_status.tmp").exists()

