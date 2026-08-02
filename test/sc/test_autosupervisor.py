"""Tests for sc auto supervisor and ensure_auto_running."""

from __future__ import annotations

import time

from sc.run import auto as auto_mod
from sc.run import instances as inst


def test_should_auto_stop_flag(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auto_mod, "sc_home_dir", lambda: tmp_path)
    monkeypatch.setattr(auto_mod, "migrate_legacy_sc_home", lambda: None)
    assert not auto_mod.should_auto_stop()
    auto_mod.request_auto_stop()
    assert auto_mod.should_auto_stop()
    auto_mod.clear_auto_stop()
    assert not auto_mod.should_auto_stop()


def test_ensure_respects_stop_flag(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auto_mod, "sc_home_dir", lambda: tmp_path)
    monkeypatch.setattr(auto_mod, "migrate_legacy_sc_home", lambda: None)
    monkeypatch.setattr(auto_mod, "leader_active_peek", lambda **_: False)
    auto_mod.request_auto_stop()
    assert auto_mod.ensure_auto_running() is False


def test_ensure_skips_when_leader_active(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auto_mod, "sc_home_dir", lambda: tmp_path)
    monkeypatch.setattr(auto_mod, "migrate_legacy_sc_home", lambda: None)
    monkeypatch.setattr(auto_mod, "read_auto_pid", lambda: None)
    monkeypatch.setattr(auto_mod, "leader_active_peek", lambda **_: True)
    spawned: list[int] = []

    def _fake_spawn(_parent):
        spawned.append(1)
        return 0

    monkeypatch.setattr(auto_mod, "_spawn_background_auto", _fake_spawn)
    assert auto_mod.ensure_auto_running() is False
    assert not spawned


def test_ensure_spawns_when_no_leader(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auto_mod, "sc_home_dir", lambda: tmp_path)
    monkeypatch.setattr(auto_mod, "migrate_legacy_sc_home", lambda: None)
    monkeypatch.setattr(auto_mod, "read_auto_pid", lambda: None)
    monkeypatch.setattr(auto_mod, "leader_active_peek", lambda **_: False)
    monkeypatch.setattr(auto_mod, "_ensure_on_cooldown", lambda: False)
    spawned: list[int] = []

    def _fake_spawn(_parent):
        spawned.append(1)
        return 0

    monkeypatch.setattr(auto_mod, "_spawn_background_auto", _fake_spawn)
    assert auto_mod.maybe_recover_auto() is True
    assert spawned == [1]


def test_recover_kills_hung_supervisor(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auto_mod, "sc_home_dir", lambda: tmp_path)
    monkeypatch.setattr(auto_mod, "migrate_legacy_sc_home", lambda: None)
    monkeypatch.setattr(auto_mod, "should_auto_stop", lambda: False)
    monkeypatch.setattr(auto_mod, "_ensure_on_cooldown", lambda: False)
    monkeypatch.setattr(auto_mod, "read_auto_pid", lambda: 9999)
    monkeypatch.setattr(auto_mod, "pid_alive", lambda _p: True)
    monkeypatch.setattr(auto_mod, "leader_active_peek", lambda **_: False)
    killed: list[int] = []
    spawned: list[int] = []

    def _kill(pid):
        killed.append(pid)

    monkeypatch.setattr(auto_mod, "_terminate_pid", _kill)
    monkeypatch.setattr(auto_mod, "_spawn_background_auto", lambda _p: spawned.append(1) or 0)
    assert auto_mod.maybe_recover_auto() is True
    assert killed == [9999]
    assert spawned == [1]


def test_peek_instances_readonly(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(inst, "home_cursor_dir", lambda: tmp_path)
    path = tmp_path / "sc_instances.json"
    now = time.time()
    path.write_text(
        '{"leader_id":"a","instances":{"a":{"pid":1,"heartbeat_at":%f,"started_at":%f}}}'
        % (now, now),
        encoding="utf-8",
    )
    doc = auto_mod.peek_instances()
    assert doc.get("leader_id") == "a"
