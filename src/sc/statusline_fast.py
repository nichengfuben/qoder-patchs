from __future__ import annotations

"""StatusLine entry + SC line formatting (compat module for -m sc.statusline_fast)."""

import json
import sys
import threading
import time
from typing import Any, Dict, List, Optional

from sc.run.status_store import display_state, read_status

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


def _infer_plan_status(d: Dict[str, Any]) -> str:
    try:
        p = float(d.get("total_pct")) if d.get("total_pct") is not None else None
    except Exception:
        p = None
    if d.get("is_unlimited"):
        return "UNLIMITED"
    if p is None:
        return "—"
    if p >= 100:
        return "LIMIT"
    if p >= 95:
        return "NEAR_LIMIT"
    return "OK"


def _plan_badge(d: Dict[str, Any]) -> tuple[str, str]:
    yellow = "\033[33m"
    red = "\033[31m"
    green = "\033[32m"
    cyan = "\033[36m"
    if d.get("_stale"):
        return "STALE", yellow
    st = str(d.get("plan_status") or "") or _infer_plan_status(d)
    colors = {
        "UNLIMITED": ("UNLIM", cyan),
        "LIMIT": ("LIMIT", red),
        "NEAR_LIMIT": ("NEAR", yellow),
        "OK": ("OK", green),
    }
    return colors.get(st, (st[:6], cyan))


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




def _read_stdin_width(timeout: float = 0.15) -> int:
    if sys.stdin is None:
        return 0
    try:
        if sys.stdin.isatty():
            return 0
    except Exception:
        return 0
    holder: List[str] = []

    def _reader() -> None:
        try:
            holder.append(sys.stdin.read() or "")
        except Exception:
            holder.append("")

    t = threading.Thread(target=_reader, daemon=True)
    t.start()
    t.join(timeout)
    if not holder:
        return 0
    raw = holder[0]
    if not raw.strip():
        return 0
    try:
        payload = json.loads(raw)
    except Exception:
        return 0
    if isinstance(payload, dict):
        try:
            return int(payload.get("render_width_chars") or 0)
        except Exception:
            return 0
    return 0


def run() -> int:
    width = _read_stdin_width()
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
