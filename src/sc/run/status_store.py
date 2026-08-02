from __future__ import annotations

"""sc 实时状态：写入 ``~/.cursor/sc_status.json``，供 statusline / ``sc status`` 读取。"""

import json
import os
import time
import uuid
from typing import Any, Dict, Optional

from sc.core.paths import migrate_legacy_sc_home, sc_home_dir

STATUS_FILE = "sc_status.json"


def status_json_path():
    migrate_legacy_sc_home()
    return sc_home_dir() / STATUS_FILE


def read_status() -> Dict[str, Any]:
    path = status_json_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _atomic_write_json(path, data: Dict[str, Any]) -> None:
    """唯一 tmp + 重试，避免多进程抢 ``sc_status.tmp`` 把 auto 打死（WinError 5）。"""
    text = json.dumps(data, ensure_ascii=False, indent=2)
    last_exc: Optional[BaseException] = None
    for attempt in range(1, 8):
        tmp = path.with_name(f"sc_status.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
        try:
            tmp.write_text(text, encoding="utf-8")
            os.replace(str(tmp), str(path))
            return
        except Exception as exc:
            last_exc = exc
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
            time.sleep(0.05 * attempt)
            try:
                path.write_text(text, encoding="utf-8")
                return
            except Exception as exc2:
                last_exc = exc2
                time.sleep(0.05 * attempt)
    try:
        print(
            f"write_status 失败 path={path} "
            f"err={type(last_exc).__name__ if last_exc else '?'}: {last_exc}",
            flush=True,
        )
    except Exception:
        pass


def write_status(**fields: Any) -> None:
    """合并写入状态。"""
    clearable = {
        "leader_id",
        "auto_pid",
        "last_error",
        "plan_message",
        "card",
        "email",
    }
    try:
        sc_home_dir().mkdir(parents=True, exist_ok=True)
        cur = read_status()
        for k, v in fields.items():
            if v is None:
                if k in clearable:
                    cur.pop(k, None)
                continue
            cur[k] = v
        cur["updated_at"] = time.time()
        cur["updated_iso"] = time.strftime("%Y-%m-%d %H:%M:%S")
        cur["pid"] = os.getpid()
        _atomic_write_json(status_json_path(), cur)
    except Exception as exc:
        try:
            print(f"write_status 异常: {type(exc).__name__}: {exc}", flush=True)
        except Exception:
            pass


def set_action(action: str, message: str = "", **extra: Any) -> None:
    write_status(action=action, message=message, **extra)


_INSTANCES = "sc_instances.json"
_STALE_AFTER_SEC = 20.0


def _leader_ttl() -> float:
    """与 instances.STALE_SEC 对齐，避免展示层与选举层判定不一致。"""
    try:
        from sc.run.instances import STALE_SEC

        return float(STALE_SEC)
    except Exception:
        return 10.0


def _read_instances_doc() -> Dict[str, Any]:
    path = sc_home_dir() / _INSTANCES
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
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
        from sc.run.instances import _instance_active

        return _instance_active(info, now=now)
    except Exception:
        try:
            hb = float(info.get("heartbeat_at") or 0)
        except Exception:
            return False
        return hb > 0 and (now - hb) < _leader_ttl()


def display_state() -> Dict[str, Any]:
    st = dict(read_status() or {})
    doc = _read_instances_doc()
    now = time.time()
    shared = doc.get("usage") if isinstance(doc, dict) else None
    if isinstance(shared, dict) and shared:
        published = float(shared.get("published_at") or 0)
        local = float(st.get("usage_fetched_at") or 0)
        if published >= local or st.get("total_pct") is None:
            for key in (
                "total_pct", "auto_pct", "api_pct", "plan_status", "membership",
                "used", "remaining", "included", "bonus", "is_unlimited", "usage_seq",
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
    st["auto_running"] = leader_ok
    st["_stale"] = (not leader_ok) or age > _STALE_AFTER_SEC
    if not st.get("action") or st.get("action") == "idle":
        if leader_ok:
            st["action"] = "polling"
        elif st.get("total_pct") is None:
            st["action"] = "idle"
            st.setdefault("message", "尚未运行 sc auto")
    return st


def run() -> int:
    from sc.statusline_fast import run as _run
    return _run()


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
