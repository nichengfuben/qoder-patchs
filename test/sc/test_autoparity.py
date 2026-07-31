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


def test_is_limit_reached_uses_usage_threshold() -> None:
    assert is_limit_reached({"total_pct": 95.0, "is_unlimited": False}, 95.0)
    assert not is_limit_reached({"total_pct": 94.9, "is_unlimited": False}, 95.0)
    assert not is_limit_reached({"total_pct": 100.0, "is_unlimited": True}, 95.0)


def test_key_pool_switch_on_daily_threshold() -> None:
    pool = KeyPool(["sc_aaa", "sc_bbb"], threshold=80, refresh_interval=60)
    cur = pool.current
    assert cur is not None
    cur.daily_used = 80
    assert pool.should_switch(cur)
    nxt = pool.switch_next()
    assert nxt is not None and nxt.key == "sc_bbb"
