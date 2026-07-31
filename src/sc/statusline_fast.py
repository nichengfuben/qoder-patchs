from __future__ import annotations

"""极速 statusLine：只读 json + 实时时钟。

由 Agent 每 ``updateIntervalMs``（默认 1s）拉起；禁止导入 api/auth/网络栈，
也不写盘，避免用量 5s 轮询或重依赖把时钟拖成「过好久才跳一秒」。
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict

from sc.status_store import format_status_lines, read_status

_INSTANCES = "sc_instances.json"


def _read_instances_doc() -> Dict[str, Any]:
    path = Path.home() / ".cursor" / _INSTANCES
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def display_state() -> Dict[str, Any]:
    """合并展示态：优先较新的 instances.usage，否则 sc_status。"""
    st = dict(read_status() or {})
    doc = _read_instances_doc()
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
                st["auto_running"] = True
    return st


def run() -> int:
    model = ""
    width = 0
    try:
        raw = sys.stdin.read()
        if raw.strip():
            payload = json.loads(raw)
            model = str(
                ((payload.get("model") or {}).get("display_name"))
                or ((payload.get("model") or {}).get("id"))
                or ""
            )
            width = int(payload.get("render_width_chars") or 0)
    except Exception:
        pass

    st = display_state()
    if not st:
        st = {"action": "idle", "message": "尚未运行 sc auto"}
    for line in format_status_lines(st, model=model, width=width):
        print(line)
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
