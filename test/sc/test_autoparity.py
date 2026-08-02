"""Tests aligning sc auto/pull helpers with Common/client.py semantics."""

from __future__ import annotations

from sc.core.api import is_limit_reached, parse_usage
from sc.core.keys import KeyPool


def test_parse_usage_avg_auto_api() -> None:
    u = parse_usage(
        {
            "membershipType": "pro",
            "isUnlimited": False,
            "individualUsage": {
                "plan": {
                    "autoPercentUsed": 100,
                    "apiPercentUsed": 0,
                    "totalPercentUsed": 81,
                    "breakdown": {"total": 161, "included": 0, "bonus": 161},
                }
            },
        }
    )
    assert u["total_pct"] == 50.0
    assert u["auto_pct"] == 100.0
    assert u["api_pct"] == 0.0
    assert u["status"] == "OK"


def test_parse_usage_both_zero_no_total_percent_fallback() -> None:
    u = parse_usage(
        {
            "individualUsage": {
                "plan": {
                    "autoPercentUsed": 0,
                    "apiPercentUsed": 0,
                    "totalPercentUsed": 81,
                    "breakdown": {},
                }
            }
        }
    )
    assert u["total_pct"] == 0.0


def test_parse_usage_ignores_api_total_percent_used() -> None:
    """即使 API 带 totalPercentUsed，也只认 (auto+api)/2。"""
    u = parse_usage(
        {
            "individualUsage": {
                "plan": {
                    "autoPercentUsed": 60,
                    "apiPercentUsed": 40,
                    "totalPercentUsed": 99,
                    "breakdown": {"total": 100},
                }
            }
        }
    )
    assert u["total_pct"] == 50.0


def test_is_limit_reached_uses_total_only() -> None:
    assert is_limit_reached({"total_pct": 95.0, "is_unlimited": False}, 95.0)
    assert not is_limit_reached({"total_pct": 94.9, "is_unlimited": False}, 95.0)
    assert not is_limit_reached({"total_pct": 100.0, "is_unlimited": True}, 95.0)
    # 仅 auto 高、total=(auto+api)/2 未达阈值 → 不换号
    assert not is_limit_reached(
        {"total_pct": 50.0, "auto_pct": 100.0, "api_pct": 0.0, "is_unlimited": False},
        90.0,
    )
    assert is_limit_reached(
        {"total_pct": 43.5, "auto_pct": 87.0, "api_pct": 0.0, "membership": "free", "is_unlimited": False},
        90.0,
    ) is False
    assert is_limit_reached(
        {"auto_pct": 87.0, "api_pct": 93.0, "is_unlimited": False},
        90.0,
    )


def test_key_pool_switch_on_daily_threshold() -> None:
    pool = KeyPool(["sc_aaa", "sc_bbb"], threshold=80, refresh_interval=60)
    cur = pool.current
    assert cur is not None
    cur.daily_used = 80
    assert pool.should_switch(cur)
    nxt = pool.switch_next()
    assert nxt is not None and nxt.key == "sc_bbb"


def test_agent_switch_requested_fresh_signal(tmp_path, monkeypatch) -> None:
    import time

    from sc.run import pull

    auth_dir = tmp_path / "Cursor"
    auth_dir.mkdir()
    monkeypatch.setattr(pull, "agent_switch_request_path", lambda: auth_dir / pull.AGENT_SWITCH_FILE)
    sig = auth_dir / pull.AGENT_SWITCH_FILE
    sig.write_text('{"ts": %d, "action": "upgrade"}' % int(time.time() * 1000), encoding="utf-8")
    assert pull.agent_switch_requested()
    pull.clear_agent_switch_request()
    assert not pull.agent_switch_requested()


def test_agent_switch_requested_stale_ignored(tmp_path, monkeypatch) -> None:
    from sc.run import pull

    auth_dir = tmp_path / "Cursor"
    auth_dir.mkdir()
    monkeypatch.setattr(pull, "agent_switch_request_path", lambda: auth_dir / pull.AGENT_SWITCH_FILE)
    sig = auth_dir / pull.AGENT_SWITCH_FILE
    sig.write_text('{"ts": 1, "action": "upgrade"}', encoding="utf-8")
    assert not pull.agent_switch_requested(max_age_sec=120.0)
