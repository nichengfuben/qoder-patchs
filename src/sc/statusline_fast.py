from __future__ import annotations

"""极速 statusLine：只读 json + 实时时钟，只输出 SC 一行。

原生路径 / 模型 / Run Everything 由 prompt-footer 渲染（footer-keep 补丁保留）；
本命令不再伪造原生行，避免与原生页脚重复。
"""

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict

from sc.status_store import format_status_lines, read_status

_INSTANCES = "sc_instances.json"
_STALE_AFTER_SEC = 20.0


def _read_instances_doc() -> Dict[str, Any]:
    path = Path.home() / ".cursor" / _INSTANCES
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _leader_fresh(doc: Dict[str, Any], *, now: float) -> bool:
    lid = doc.get("leader_id")
    if not lid:
        return False
    info = (doc.get("instances") or {}).get(lid)
    if not isinstance(info, dict):
        return False
    try:
        hb = float(info.get("heartbeat_at") or 0)
    except Exception:
        return False
    return hb > 0 and (now - hb) < 10.0


def display_state() -> Dict[str, Any]:
    """合并展示态：优先较新的 instances.usage，否则 sc_status。"""
    st = dict(read_status() or {})
    doc = _read_instances_doc()
    now = time.time()
    shared = doc.get("usage") if isinstance(doc, dict) else None
    if isinstance(shared, dict) and shared:
        published = float(shared.get("published_at") or 0)
        local = float(st.get("usage_fetched_at") or 0)
        if published >= local or st.get("total_pct") is None:
            for key in (
                "total_pct",
                "auto_pct",
                "api_pct",
                "plan_status",
                "membership",
                "used",
                "remaining",
                "included",
                "bonus",
                "is_unlimited",
                "usage_seq",
            ):
                if shared.get(key) is not None:
                    st[key] = shared[key]
            if shared.get("total") is not None:
                st["total_tokens"] = shared["total"]
            if published > 0:
                st["usage_fetched_at"] = published
            if doc.get("leader_id"):
                st["leader_id"] = doc.get("leader_id")

    fetched = float(st.get("usage_fetched_at") or 0)
    age = (now - fetched) if fetched > 0 else 1e9
    leader_ok = _leader_fresh(doc, now=now)
    # 仅以 leader 心跳判定 auto 是否在跑；json 里的 auto_running 可能是僵尸 true
    st["auto_running"] = leader_ok
    # STALE：无 leader，或用量过旧（leader 在但久未成功刷新）
    st["_stale"] = (not leader_ok) or age > _STALE_AFTER_SEC
    if not st.get("action") or st.get("action") == "idle":
        if leader_ok:
            st["action"] = "polling"
        elif st.get("total_pct") is None:
            st["action"] = "idle"
            st.setdefault("message", "尚未运行 sc auto")
    return st


def run() -> int:
    width = 0
    try:
        raw = sys.stdin.read()
        if raw.strip():
            payload = json.loads(raw)
            if isinstance(payload, dict):
                width = int(payload.get("render_width_chars") or 0)
    except Exception:
        pass

    st = display_state()
    if not st:
        st = {"action": "idle", "message": "尚未运行 sc auto", "_stale": True}
    # 只输出 SC 行；模型/路径/模式留给原生 footer
    for line in format_status_lines(st, width=width):
        print(line)
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
