from __future__ import annotations

"""sc 实时状态：写入与 auth 同级的 ``sc_status.json``，供 statusline / ``sc status`` 读取。"""

import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from sc.core.paths import cursor_config_dir

STATUS_FILE = "sc_status.json"


def status_json_path():
    return cursor_config_dir() / STATUS_FILE


def read_status() -> Dict[str, Any]:
    path = status_json_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
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
        cursor_config_dir().mkdir(parents=True, exist_ok=True)
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


def _pct(v: Any) -> str:
    if v is None:
        return "-"
    try:
        return f"{float(v):.1f}%"
    except Exception:
        return str(v)


def _bar(pct: Any, width: int = 30) -> str:
    try:
        p = max(0.0, min(100.0, float(pct)))
    except Exception:
        return "[" + ("░" * width) + "]"
    filled = int(width * p / 100.0)
    return "[" + ("█" * filled) + ("░" * (width - filled)) + "]"


def _plan_badge(d: Dict[str, Any]) -> tuple[str, str]:
    yellow = "\033[33m"
    red = "\033[31m"
    green = "\033[32m"
    cyan = "\033[36m"
    if d.get("_stale"):
        return "STALE", yellow
    st = str(d.get("plan_status") or "")
    if not st:
        try:
            p = float(d.get("total_pct")) if d.get("total_pct") is not None else None
        except Exception:
            p = None
        if d.get("is_unlimited"):
            st = "UNLIMITED"
        elif p is None:
            st = "—"
        elif p >= 100:
            st = "LIMIT"
        elif p >= 95:
            st = "NEAR_LIMIT"
        else:
            st = "OK"
    if st == "UNLIMITED":
        return "UNLIM", cyan
    if st == "LIMIT":
        return "LIMIT", red
    if st == "NEAR_LIMIT":
        return "NEAR", yellow
    if st == "OK":
        return "OK", green
    return st[:6], cyan


def _visible_len(s: str) -> int:
    out = 0
    i = 0
    while i < len(s):
        if s[i] == "\033":
            j = s.find("m", i)
            i = j + 1 if j >= 0 else i + 1
            continue
        out += 1
        i += 1
    return out


def _truncate_ansi(s: str, width: int) -> str:
    if _visible_len(s) <= width:
        return s
    plain: list[str] = []
    i = 0
    while i < len(s) and len(plain) < max(0, width - 1):
        if s[i] == "\033":
            j = s.find("m", i)
            if j < 0:
                break
            i = j + 1
            continue
        plain.append(s[i])
        i += 1
    return "".join(plain) + "…\033[0m"


def _is_transient_err(err_s: str) -> bool:
    low = err_s.lower()
    return (
        "urlopen" in low
        or "unexpected_eof" in low
        or "ssl" in low
        or err_s in ("SSL断连", "SSL失败", "超时", "网络错误", "连接重置", "DNS失败")
    )


def _format_pull_line(d: Dict[str, Any], *, model: str) -> list[str]:
    dim = "\033[90m"
    cyan = "\033[36m"
    yellow = "\033[33m"
    bold = "\033[1m"
    reset = "\033[0m"
    action = str(d.get("action") or "idle")
    threshold = d.get("usage_threshold")
    tick_n = d.get("usage_seq") or d.get("poll_n")
    tick = f"#{tick_n}" if tick_n is not None else ""
    clock = time.strftime("%H:%M:%S")
    msg = str(d.get("message") or "").strip()
    label = "SWITCH" if action == "switching" else "PULL"
    line = f"{cyan}SC{reset} {bold}{yellow}{label}{reset}"
    if threshold is not None:
        line += f" thr>={threshold}%"
    if tick:
        line += f" {tick}"
    line += f" {dim}{clock}{reset}"
    if msg:
        short = msg if len(msg) <= 28 else msg[:27] + "…"
        line += f" {yellow}{short}{reset}"
    return [line]


def _format_error_line(d: Dict[str, Any], *, model: str) -> list[str]:
    dim = "\033[90m"
    cyan = "\033[36m"
    red = "\033[31m"
    reset = "\033[0m"
    err = str(d.get("last_error") or "").strip()
    msg = str(d.get("message") or "").strip()
    err_s = err or msg or "error"
    tick_n = d.get("usage_seq") or d.get("poll_n")
    tick = f"#{tick_n}" if tick_n is not None else ""
    clock = time.strftime("%H:%M:%S")
    total = d.get("total_pct")
    badge, badge_color = _plan_badge(d)
    bar = _bar(total)
    usage = f"{bar} {_pct(total)}"
    if _is_transient_err(err_s):
        line = f"{cyan}SC{reset} {badge_color}{badge}{reset} {usage}"
        if tick:
            line += f" {tick}"
        line += f" {dim}{clock}{reset}"
        if model:
            line += f" {dim}{model}{reset}"
        return [line]
    if len(err_s) > 20:
        err_s = err_s[:19] + "…"
    line = f"{cyan}SC{reset} {red}ERR{reset} {red}{err_s}{reset}"
    if tick:
        line += f" {tick}"
    line += f" {dim}{clock}{reset}"
    return [line]


def _format_normal_line(d: Dict[str, Any], *, model: str) -> list[str]:
    dim = "\033[90m"
    cyan = "\033[36m"
    reset = "\033[0m"
    total = d.get("total_pct")
    tick_n = d.get("usage_seq") or d.get("poll_n")
    tick = f"#{tick_n}" if tick_n is not None else ""
    clock = time.strftime("%H:%M:%S")
    badge, badge_color = _plan_badge(d)
    bar = _bar(total)
    usage = f"{bar} {_pct(total)}"
    line = f"{cyan}SC{reset} {badge_color}{badge}{reset} {usage}"
    if tick:
        line += f" {tick}"
    line += f" {dim}{clock}{reset}"
    if model:
        line += f" {dim}{model}{reset}"
    return [line]


def format_status_lines(
    data: Optional[Dict[str, Any]] = None,
    *,
    model: str = "",
    width: int = 0,
    cwd: str = "",
    mode: str = "",
    context_pct: Any = None,
) -> list[str]:
    """仅 SC 一行：``SC OK [████…] 66.0% #126 HH:MM:SS``。"""
    d = data if data is not None else read_status()
    _ = (cwd, mode, context_pct)
    action = str(d.get("action") or "idle")
    if action in ("pulling", "switching"):
        lines = _format_pull_line(d, model=model)
    elif action == "error":
        lines = _format_error_line(d, model=model)
    else:
        lines = _format_normal_line(d, model=model)
    if width and width > 24:
        lines = [
            ln if _visible_len(ln) <= width else _truncate_ansi(ln, width) for ln in lines
        ]
    return lines


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
    for line in format_status_lines(st, width=width):
        print(line)
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
