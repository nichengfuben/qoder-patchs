"""Tests for multi-instance leader election (latest online wins)."""

from __future__ import annotations

import json

from sc import instances as inst


def test_elect_latest_started_is_leader(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(inst, "home_cursor_dir", lambda: tmp_path)
    now = 1_000_000.0
    data = {
        "version": 1,
        "instances": {
            "old": {"started_at": 100.0, "heartbeat_at": now - 1, "pid": 1},
            "new": {"started_at": 200.0, "heartbeat_at": now - 1, "pid": 2},
        },
        "leader_id": None,
        "usage": {},
    }
    monkeypatch.setattr(inst, "_pid_alive", lambda pid: True)
    leader = inst._elect(data, now=now)
    assert leader == "new"
    assert data["leader_id"] == "new"
    assert data["instances"]["new"]["role"] == "leader"
    assert data["instances"]["old"]["role"] == "follower"


def test_elect_single_instance(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(inst, "home_cursor_dir", lambda: tmp_path)
    monkeypatch.setattr(inst, "_pid_alive", lambda pid: True)
    now = 1_000_000.0
    data = {
        "version": 1,
        "instances": {
            "only": {"started_at": 50.0, "heartbeat_at": now - 2, "pid": 9},
        },
        "leader_id": None,
        "usage": {},
    }
    assert inst._elect(data, now=now) == "only"


def test_elect_ignores_stale_even_if_started_later(tmp_path, monkeypatch) -> None:
    """过期实例不参与选举，即使 started_at 更晚。"""
    monkeypatch.setattr(inst, "home_cursor_dir", lambda: tmp_path)
    now = 1_000_000.0
    data = {
        "version": 1,
        "instances": {
            "fresh": {"started_at": 100.0, "heartbeat_at": now - 2, "pid": 1},
            "stale_but_late": {"started_at": 999.0, "heartbeat_at": now - 10, "pid": 2},
        },
        "leader_id": None,
        "usage": {},
    }
    assert inst._elect(data, now=now) == "fresh"
    assert "stale_but_late" in data["instances"]


def test_leader_prune_clears_stale_timestamp(tmp_path, monkeypatch) -> None:
    """仅 leader：now - hb >= 10 直接清。"""
    monkeypatch.setattr(inst, "home_cursor_dir", lambda: tmp_path)
    monkeypatch.setattr(inst, "_pid_alive", lambda pid: True)
    now = 1_000_000.0
    data = {
        "version": 1,
        "instances": {
            "leader": {"started_at": now - 5, "heartbeat_at": now - 1, "pid": 1},
            "dead": {"started_at": now - 20, "heartbeat_at": now - 10, "pid": 2},
        },
        "leader_id": "leader",
        "usage": {},
    }
    removed = inst._prune_by_timestamp(data, now=now)
    assert removed == ["dead"]
    assert "dead" not in data["instances"]
    assert "leader" in data["instances"]


def test_follower_clears_stale_leader(tmp_path, monkeypatch) -> None:
    """非 leader：now - leader.hb >= 10 → 清实例 + Leader，再选举。"""
    monkeypatch.setattr(inst, "home_cursor_dir", lambda: tmp_path)
    monkeypatch.setattr(inst, "_pid_alive", lambda pid: True)
    now = 1_000_000.0
    data = {
        "version": 1,
        "instances": {
            "old_leader": {
                "started_at": now - 30,
                "heartbeat_at": now - 10,
                "pid": 1,
            },
            "follower": {
                "started_at": now - 5,
                "heartbeat_at": now - 1,
                "pid": 2,
            },
        },
        "leader_id": "old_leader",
        "usage": {"leader_id": "old_leader", "published_at": now - 10, "total_pct": 1},
    }
    (tmp_path / "sc_instances.json").write_text(
        json.dumps(data), encoding="utf-8"
    )
    monkeypatch.setattr(inst.time, "time", lambda: now)
    out = inst.follower_clear_stale_leader("follower")
    assert "old_leader" not in (out.get("instances") or {})
    assert out.get("leader_id") == "follower"
    assert out.get("last_follower_cleared") == "old_leader"


def test_elect_empty(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(inst, "home_cursor_dir", lambda: tmp_path)
    data = {"version": 1, "instances": {}, "leader_id": "x", "usage": {}}
    assert inst._elect(data) is None
    assert data["leader_id"] is None
