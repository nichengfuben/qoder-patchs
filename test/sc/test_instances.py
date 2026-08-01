"""Tests for multi-instance leader election (latest online wins)."""

from __future__ import annotations

import json

from sc.run import instances as inst


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
    """死进程过期不参与选举，即使 started_at 更晚。"""
    monkeypatch.setattr(inst, "home_cursor_dir", lambda: tmp_path)
    monkeypatch.setattr(inst, "_pid_alive", lambda pid: pid == 1)
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


def test_elect_keeps_alive_pid_during_grace(tmp_path, monkeypatch) -> None:
    """活进程在宽限内即使心跳过期仍参与选举（长请求不掉 leader）。"""
    monkeypatch.setattr(inst, "home_cursor_dir", lambda: tmp_path)
    monkeypatch.setattr(inst, "_pid_alive", lambda pid: True)
    now = 1_000_000.0
    data = {
        "version": 1,
        "instances": {
            "busy": {"started_at": 100.0, "heartbeat_at": now - 60, "pid": 7},
        },
        "leader_id": None,
        "usage": {},
    }
    assert inst._elect(data, now=now) == "busy"


def test_leader_prune_clears_stale_timestamp(tmp_path, monkeypatch) -> None:
    """死进程且 hb 过期才清；活进程宽限内保留。"""
    monkeypatch.setattr(inst, "home_cursor_dir", lambda: tmp_path)
    monkeypatch.setattr(inst, "_pid_alive", lambda pid: pid == 1)
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
    """非 leader：旧 leader 进程已死且 hb 过期 → 清实例再选举。"""
    monkeypatch.setattr(inst, "home_cursor_dir", lambda: tmp_path)
    monkeypatch.setattr(inst, "_pid_alive", lambda pid: pid == 2)
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
    from sc.run.autoloop import follower_clear_stale_leader

    out = follower_clear_stale_leader("follower")
    assert "old_leader" not in (out.get("instances") or {})
    assert out.get("leader_id") == "follower"
    assert out.get("last_follower_cleared") == "old_leader"


def test_elect_empty(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(inst, "home_cursor_dir", lambda: tmp_path)
    data = {"version": 1, "instances": {}, "leader_id": "x", "usage": {}}
    assert inst._elect(data) is None
    assert data["leader_id"] is None


def test_mutate_refreshes_caller_heartbeat(tmp_path, monkeypatch) -> None:
    """publish/snapshot 路径走 mutate 时刷新本进程心跳，避免长请求自我掉 leader。"""
    monkeypatch.setattr(inst, "home_cursor_dir", lambda: tmp_path)
    monkeypatch.setattr(inst, "_pid_alive", lambda pid: True)
    now = 1_000_000.0
    monkeypatch.setattr(inst.time, "time", lambda: now)
    iid = "self"
    data0 = {
        "version": 1,
        "instances": {
            iid: {
                "started_at": now - 60,
                "heartbeat_at": now - 9,
                "pid": __import__("os").getpid(),
                "role": "leader",
            }
        },
        "leader_id": iid,
        "usage": {},
    }
    (tmp_path / "sc_instances.json").write_text(
        __import__("json").dumps(data0), encoding="utf-8"
    )

    def _bump(data):
        data["usage"] = {"total_pct": 1.0, "published_at": now}

    out = inst.mutate(_bump)
    assert out["leader_id"] == iid
    assert out["instances"][iid]["heartbeat_at"] == now


def test_still_leader_heartbeats(tmp_path, monkeypatch) -> None:
    from sc.run.auto import still_leader

    monkeypatch.setattr(inst, "home_cursor_dir", lambda: tmp_path)
    monkeypatch.setattr(inst, "_pid_alive", lambda pid: True)
    now = 1_000_000.0
    clock = {"t": now}

    def _time():
        return clock["t"]

    monkeypatch.setattr(inst.time, "time", _time)
    iid = "only"
    (tmp_path / "sc_instances.json").write_text(
        __import__("json").dumps(
            {
                "version": 1,
                "instances": {
                    iid: {
                        "started_at": now - 30,
                        "heartbeat_at": now - 9,
                        "pid": __import__("os").getpid(),
                        "role": "leader",
                    }
                },
                "leader_id": iid,
                "usage": {},
            }
        ),
        encoding="utf-8",
    )
    clock["t"] = now + 5  # 若无心跳刷新会 stale
    assert still_leader(iid) is True
    doc = inst.read_instances()
    assert doc["leader_id"] == iid
    assert doc["instances"][iid]["heartbeat_at"] == clock["t"]
