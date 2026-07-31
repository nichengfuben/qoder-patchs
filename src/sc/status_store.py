from __future__ import annotations

"""sc 实时状态：写入与 auth 同级的 ``sc_status.json``，供 statusline / ``sc status`` 读取。"""

import json
import os
import time
import uuid
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
    # 绝不抛出：status 写失败不应杀死 sc auto / statusline
    try:
        print(
            f"write_status 失败 path={path} "
            f"err={type(last_exc).__name__ if last_exc else '?'}: {last_exc}",
            flush=True,
        )
    except Exception:
        pass


def write_status(**fields: Any) -> None:
    """合并写入状态。

    默认跳过值为 ``None`` 的键；下列键传入 ``None`` 时会**清除**残留，
    避免 leader/auto 下线后 statusline 仍显示僵尸状态。
    """
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


def _pct(v: Any) -> str:
    if v is None:
        return "-"
    try:
        return f"{float(v):.1f}%"
    except Exception:
        return str(v)


def _bar(pct: Any, width: int = 30) -> str:
    """对齐 Common/client.py：`[████…░░░░…]`。"""
    try:
        p = max(0.0, min(100.0, float(pct)))
    except Exception:
        return "[" + ("░" * width) + "]"
    filled = int(width * p / 100.0)
    return "[" + ("█" * filled) + ("░" * (width - filled)) + "]"


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
    # auto 停了或用量太旧：先标 STALE，避免和 client 实时 /usage 对不上却仍显示 OK
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


def format_status_lines(
    data: Optional[Dict[str, Any]] = None,
    *,
    model: str = "",
    width: int = 0,
    cwd: str = "",
    mode: str = "",
    context_pct: Any = None,
) -> list[str]:
    """仅 SC 一行：``SC OK [████…] 66.0% #126 HH:MM:SS``。

    路径 / 模型 / Run Everything 由原生 prompt-footer 负责（footer-keep）。
    ``cwd``/``mode``/``context_pct`` 保留兼容，忽略。
    """
    d = data if data is not None else read_status()
    dim = "\033[90m"
    cyan = "\033[36m"
    yellow = "\033[33m"
    red = "\033[31m"
    bold = "\033[1m"
    reset = "\033[0m"
    _ = (cwd, mode, context_pct)

    action = str(d.get("action") or "idle")
    total = d.get("total_pct")
    tick_n = d.get("usage_seq")
    if tick_n is None:
        tick_n = d.get("poll_n")
    threshold = d.get("usage_threshold")
    err = str(d.get("last_error") or "").strip()
    msg = str(d.get("message") or "").strip()
    badge, badge_color = _plan_badge(d)

    bar = _bar(total)
    usage = f"{bar} {_pct(total)}"
    tick = f"#{tick_n}" if tick_n is not None else ""
    clock = time.strftime("%H:%M:%S")

    if action in ("pulling", "switching"):
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
        lines = [line]
    elif action == "error":
        err_s = err or msg or "error"
        low = err_s.lower()
        if (
            "urlopen" in low
            or "unexpected_eof" in low
            or "ssl" in low
            or err_s
            in ("SSL断连", "SSL失败", "超时", "网络错误", "连接重置", "DNS失败")
        ):
            line = f"{cyan}SC{reset} {badge_color}{badge}{reset} {usage}"
            if tick:
                line += f" {tick}"
            line += f" {dim}{clock}{reset}"
            if model:
                line += f" {dim}{model}{reset}"
            lines = [line]
        else:
            if len(err_s) > 20:
                err_s = err_s[:19] + "…"
            line = f"{cyan}SC{reset} {red}ERR{reset} {red}{err_s}{reset}"
            if tick:
                line += f" {tick}"
            line += f" {dim}{clock}{reset}"
            lines = [line]
    else:
        line = f"{cyan}SC{reset} {badge_color}{badge}{reset} {usage}"
        if tick:
            line += f" {tick}"
        line += f" {dim}{clock}{reset}"
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
