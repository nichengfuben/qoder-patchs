from __future__ import annotations

"""sc 实时状态：写入与 auth 同级的 ``sc_status.json``，供 statusline / ``sc status`` 读取。"""

import json
import os
import time
from typing import Any, Dict, Optional

from sc.paths import cursor_config_dir

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


def write_status(**fields: Any) -> None:
    """合并写入状态。``fields`` 中值为 ``None`` 的键会被跳过（不覆盖）。"""
    cursor_config_dir().mkdir(parents=True, exist_ok=True)
    cur = read_status()
    for k, v in fields.items():
        if v is not None:
            cur[k] = v
    cur["updated_at"] = time.time()
    cur["updated_iso"] = time.strftime("%Y-%m-%d %H:%M:%S")
    cur["pid"] = os.getpid()
    path = status_json_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cur, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def set_action(action: str, message: str = "", **extra: Any) -> None:
    write_status(action=action, message=message, **extra)


def _pct(v: Any) -> str:
    if v is None:
        return "-"
    try:
        return f"{float(v):.1f}%"
    except Exception:
        return str(v)


def _bar(pct: Any, width: int = 10) -> str:
    try:
        p = max(0.0, min(100.0, float(pct)))
    except Exception:
        return "[" + ("." * width) + "]"
    filled = int(round(width * p / 100.0))
    # ASCII：避免 Windows GBK 控制台无法显示 ░█
    return "[" + ("#" * filled) + ("." * (width - filled)) + "]"


def _short_email(email: str, max_len: int = 18) -> str:
    e = (email or "-").strip() or "-"
    if len(e) <= max_len:
        return e
    if "@" in e:
        local, _, domain = e.partition("@")
        keep = max(3, max_len - len(domain) - 2)
        return f"{local[:keep]}…@{domain}"
    return e[: max_len - 1] + "…"


def _plan_badge(d: Dict[str, Any]) -> tuple[str, str]:
    """返回 (彩色标签, ANSI色)。对齐 client: OK / NEAR_LIMIT / LIMIT / UNLIMITED。"""
    yellow = "\033[33m"
    red = "\033[31m"
    green = "\033[32m"
    cyan = "\033[36m"
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


def format_status_lines(
    data: Optional[Dict[str, Any]] = None,
    *,
    model: str = "",
    width: int = 0,
) -> list[str]:
    """紧凑一行（必要时两行）：完整但不占空间，突出刷新额度 / 换号。"""
    d = data if data is not None else read_status()
    dim = "\033[90m"
    cyan = "\033[36m"
    green = "\033[32m"
    yellow = "\033[33m"
    red = "\033[31m"
    bold = "\033[1m"
    reset = "\033[0m"

    action = str(d.get("action") or "idle")
    auto_on = bool(d.get("auto_running"))
    email = _short_email(str(d.get("email") or "-"))
    membership = str(d.get("membership") or d.get("card") or "-")
    if membership == "-":
        membership = str(d.get("card") or "-")
    total = d.get("total_pct")
    auto_pct = d.get("auto_pct")
    api_pct = d.get("api_pct")
    poll_n = d.get("poll_n")
    threshold = d.get("usage_threshold")
    err = str(d.get("last_error") or "").strip()
    msg = str(d.get("message") or "").strip()
    badge, badge_color = _plan_badge(d)

    auto_mark = f"{green}A{reset}" if auto_on else f"{dim}-{reset}"
    bar = _bar(total)
    usage = f"{_pct(total)} {bar}"
    detail = f"a{_pct(auto_pct)} p{_pct(api_pct)}"
    acct = f"{email}" + (f"/{membership}" if membership and membership != "-" else "")
    tick = f"#{poll_n}" if poll_n is not None else ""

    # ── 换号 / 拉号：高亮一行 ──────────────────────────────────────────
    if action in ("pulling", "switching"):
        label = "SWITCH" if action == "switching" else "PULL"
        line = (
            f"{cyan}SC{reset} {bold}{yellow}{label}{reset} "
            f"{usage} thr>={threshold if threshold is not None else 95}% "
            f"→ {acct}"
        )
        if tick:
            line += f" {dim}{tick}{reset}"
        if msg:
            # 只留短事件语
            short = msg if len(msg) <= 36 else msg[:35] + "…"
            line += f" {yellow}{short}{reset}"
        lines = [line]
    # ── 刷新额度（polling）：突出 ↻ ───────────────────────────────────
    elif action == "polling":
        line = (
            f"{cyan}SC{reset} {auto_mark} {green}↻{reset}{tick or ''} "
            f"{badge_color}{badge}{reset} {usage} {dim}{detail}{reset} {acct}"
        )
        lines = [line]
    # ── 错误：一行 ────────────────────────────────────────────────────
    elif action == "error":
        err_s = err or msg or "error"
        if len(err_s) > 42:
            err_s = err_s[:41] + "…"
        line = (
            f"{cyan}SC{reset} {auto_mark} {red}ERR{reset} {usage} {acct} "
            f"{red}{err_s}{reset}"
        )
        lines = [line]
    # ── 常态：一行完整摘要 ────────────────────────────────────────────
    else:
        line = (
            f"{cyan}SC{reset} {auto_mark} {badge_color}{badge}{reset} "
            f"{usage} {dim}{detail}{reset} {acct}"
        )
        if tick:
            line += f" {dim}{tick}{reset}"
        if model:
            line += f" {dim}{model}{reset}"
        lines = [line]

    if width and width > 24:
        lines = [
            ln if _visible_len(ln) <= width else _truncate_ansi(ln, width) for ln in lines
        ]
    return lines


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
