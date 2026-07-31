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


def format_status_lines(
    data: Optional[Dict[str, Any]] = None,
    *,
    model: str = "",
    width: int = 0,
) -> list[str]:
    """生成 statusline 多行文本（含 ANSI 淡色）。"""
    d = data if data is not None else read_status()
    dim = "\033[90m"
    cyan = "\033[36m"
    green = "\033[32m"
    yellow = "\033[33m"
    red = "\033[31m"
    reset = "\033[0m"

    auto_on = bool(d.get("auto_running"))
    action = str(d.get("action") or "idle")
    msg = str(d.get("message") or "")
    email = str(d.get("email") or "-")
    card = str(d.get("card") or "-")
    uid = str(d.get("uid") or "-")
    if len(uid) > 12:
        uid = uid[:6] + "…" + uid[-4:]
    total = d.get("total_pct")
    auto_pct = d.get("auto_pct")
    api_pct = d.get("api_pct")
    poll_n = d.get("poll_n")
    interval = d.get("poll_interval")
    threshold = d.get("usage_threshold")
    auto_pid = d.get("auto_pid")
    err = str(d.get("last_error") or "")
    updated = str(d.get("updated_iso") or "-")
    keys_n = d.get("keys")

    def pct(v: Any) -> str:
        if v is None:
            return "-"
        try:
            return f"{float(v):.1f}%"
        except Exception:
            return str(v)

    if action in ("pulling", "switching"):
        act_color = yellow
    elif action in ("error",):
        act_color = red
    elif action in ("polling", "ok"):
        act_color = green
    else:
        act_color = cyan

    auto_txt = f"{green}ON{reset} pid={auto_pid or '?'}" if auto_on else f"{dim}OFF{reset}"
    line1 = (
        f"{cyan}SC{reset} auto={auto_txt}  "
        f"act={act_color}{action}{reset}"
    )
    if poll_n is not None:
        line1 += f"  #{poll_n}"
    if interval is not None:
        line1 += f"  poll={interval}s"
    if threshold is not None:
        line1 += f"  thr={threshold}%"
    if keys_n is not None:
        line1 += f"  keys={keys_n}"

    line2 = (
        f"{dim}acct{reset} {email}  card={card}  uid={uid}  "
        f"usage total={pct(total)} auto={pct(auto_pct)} api={pct(api_pct)}"
    )

    line3_parts = []
    if msg:
        line3_parts.append(msg)
    if err:
        line3_parts.append(f"{red}err:{err}{reset}")
    line3_parts.append(f"{dim}upd {updated}{reset}")
    if model:
        line3_parts.append(f"{dim}model {model}{reset}")
    line3 = "  |  ".join(line3_parts)

    lines = [line1, line2, line3]
    if width and width > 20:
        lines = [ln if _visible_len(ln) <= width else _truncate_ansi(ln, width) for ln in lines]
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
    # naive strip then pad with reset
    plain = []
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
