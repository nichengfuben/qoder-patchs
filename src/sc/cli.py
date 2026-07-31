from __future__ import annotations

"""`/sc` 便携命令：拉号 / 用量 / 后台轮询换号 + statusline 状态。"""

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import List, Optional

from sc import api, auth
from sc.config import load_config, save_config
from sc.paths import auth_json_path, config_json_path, cursor_config_dir
from sc.status_store import (
    format_status_lines,
    read_status,
    set_action,
    status_json_path,
    write_status,
)

PID_FILE = "sc_auto.pid"


def _normalize_argv(argv: List[str]) -> List[str]:
    """支持 ``/sc pull`` 与 ``sc pull`` / ``pull``。"""
    out = list(argv)
    while out and out[0] in ("/sc", "sc"):
        out = out[1:]
    if out and out[0].startswith("/") and out[0] != "/":
        out[0] = out[0][1:]
    return out


def _mask(key: str) -> str:
    return f"{key[:6]}...{key[-4:]}" if len(key) > 10 else key


def _snapshot_account(access: Optional[str] = None, email: str = "", card: str = "") -> None:
    token = access or auth.access_token()
    uid = api.extract_user_id(token) if token else ""
    cfg = load_config()
    write_status(
        email=email or None,
        card=card or None,
        uid=uid or None,
        keys=len(cfg.get("api_keys") or []),
        poll_interval=cfg.get("poll_interval"),
        usage_threshold=cfg.get("usage_threshold"),
        auto_running=bool(_read_auto_pid()),
        auto_pid=_read_auto_pid(),
        auth_path=str(auth_json_path()),
        config_path=str(config_json_path()),
        status_path=str(status_json_path()),
    )


def _snapshot_usage(usage: dict) -> None:
    write_status(
        total_pct=usage.get("total_pct"),
        auto_pct=usage.get("auto_pct"),
        api_pct=usage.get("api_pct"),
        included=usage.get("included"),
        bonus=usage.get("bonus"),
        total_tokens=usage.get("total"),
        used=usage.get("used"),
        remaining=usage.get("remaining"),
        plan_status=usage.get("status"),
        membership=usage.get("membership"),
        is_unlimited=usage.get("is_unlimited"),
        plan_message=usage.get("message") or None,
    )


def cmd_pull() -> int:
    cfg = load_config()
    keys = list(cfg.get("api_keys") or [])
    if not keys:
        set_action("error", "无 API Key", last_error="missing api key")
        print("无 API Key。请先: sc addkey <sc_xxx> 或编辑", config_json_path())
        return 1
    threshold = float(cfg.get("usage_threshold") or 95.0)
    retries = int(cfg.get("max_retry_per_pull") or 3)
    timeout = float(cfg.get("request_timeout") or 20)
    base = str(cfg.get("base_url") or "")
    _snapshot_account()
    for attempt in range(1, retries + 1):
        key = keys[(attempt - 1) % len(keys)]
        set_action(
            "pulling",
            f"pull [{attempt}/{retries}] via {_mask(key)}",
            last_error="",
        )
        print(f"[{attempt}/{retries}] pull via {_mask(key)} ...")
        try:
            data = api.pull_token(base, key, timeout=timeout)
        except Exception as exc:
            set_action("error", f"pull 失败: {exc}", last_error=str(exc))
            print(f"pull 失败: {exc}")
            continue
        access, refresh, email, card = api.extract_tokens(data)
        if not access:
            set_action("error", "响应无 access_token", last_error="no access_token")
            print("响应无 access_token")
            continue
        if not auth.write_auth(access, refresh):
            set_action("error", "写入 auth.json 失败", last_error="write auth failed")
            print("写入 auth.json 失败:", auth_json_path())
            return 1
        _snapshot_account(access, email=email, card=card)
        write_status(last_pull_at=time.strftime("%Y-%m-%d %H:%M:%S"), last_error="")
        print(f"已写入 {auth_json_path()} email={email} card={card}")
        print("(已打 cursor-agent 热更新补丁时无需重启)")
        try:
            usage = api.parse_usage(api.fetch_usage(access, timeout=timeout))
            _snapshot_usage(usage)
            print(f"用量 total={usage['total_pct']}%")
            if not api.is_limit_reached(usage, threshold):
                set_action("ok", f"pull 成功 total={usage['total_pct']}%")
                return 0
            set_action("switching", f"超阈值 (>={threshold}%)，继续拉号")
            print(f"超阈值 (>={threshold}%)，继续拉号...")
        except Exception as exc:
            set_action("ok", f"已换号，用量查询失败: {exc}", last_error=str(exc))
            print(f"用量查询失败(仍保留本次 token): {exc}")
            return 0
    set_action("error", "pull 重试耗尽", last_error="retries exhausted")
    return 1


def cmd_usage() -> int:
    token = auth.access_token()
    if not token:
        set_action("error", "本地无 Token", last_error="no token")
        print("本地无 Token，先 sc pull")
        return 1
    set_action("polling", "查询用量…")
    try:
        usage = api.parse_usage(api.fetch_usage(token))
    except Exception as exc:
        set_action("error", f"查询失败: {exc}", last_error=str(exc))
        print(f"查询失败: {exc}")
        return 1
    _snapshot_account(token)
    _snapshot_usage(usage)
    set_action("ok", f"usage total={usage['total_pct']}%")
    print(f"auth: {auth_json_path()}")
    print(f"total={usage['total_pct']}% auto={usage['auto_pct']}% api={usage['api_pct']}%")
    return 0


def cmd_token() -> int:
    token = auth.access_token()
    path = auth_json_path()
    if not token:
        set_action("error", "未找到 Token", last_error="no token")
        print(f"未找到 Token ({path})")
        return 1
    uid = api.extract_user_id(token)
    _snapshot_account(token)
    set_action("ok", f"token uid={uid or '-'}")
    print(f"path={path}\nuid={uid or '-'}\ntoken={_mask(token)}")
    return 0


def cmd_addkey(key: str) -> int:
    cfg = load_config()
    keys = list(cfg.get("api_keys") or [])
    if key in keys:
        print("Key 已存在")
        _snapshot_account()
        return 0
    keys.append(key)
    cfg["api_keys"] = keys
    save_config(cfg)
    _snapshot_account()
    set_action("ok", f"已添加 {_mask(key)}")
    print(f"已添加 {_mask(key)} → {config_json_path()}")
    return 0


def cmd_status() -> int:
    cfg = load_config()
    keys = cfg.get("api_keys") or []
    auto_pid = _read_auto_pid()
    _snapshot_account()
    write_status(auto_running=bool(auto_pid), auto_pid=auto_pid, keys=len(keys))
    # 尽量刷新用量
    token = auth.access_token()
    if token:
        try:
            usage = api.parse_usage(api.fetch_usage(token))
            _snapshot_usage(usage)
            set_action(
                "ok" if not auto_pid else "polling",
                f"status total={usage['total_pct']}%",
            )
        except Exception as exc:
            set_action("ok" if not auto_pid else "polling", "status（用量刷新失败）", last_error=str(exc))
    else:
        set_action("idle", "无 Token")

    print(f"config: {config_json_path()}")
    print(f"auth:   {auth_json_path()}")
    print(f"status: {status_json_path()}")
    print(f"keys:   {len(keys)}")
    for k in keys:
        print(f"  - {_mask(str(k))}")
    print(f"poll={cfg.get('poll_interval')}s threshold={cfg.get('usage_threshold')}%")
    if auto_pid:
        print(f"auto:   running pid={auto_pid}")
    else:
        print("auto:   stopped")
    st = read_status()
    print("--- live ---")
    for line in format_status_lines(st):
        # strip ANSI for plain CLI print
        plain = line
        while "\033[" in plain:
            a = plain.find("\033[")
            b = plain.find("m", a)
            if b < 0:
                break
            plain = plain[:a] + plain[b + 1 :]
        print(plain)
    return 0


def cmd_statusline() -> int:
    """供 Cursor Agent ``statusLine.command`` 调用：stdin JSON → stdout 多行。"""
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
    st = read_status()
    # 无状态文件时给默认行，避免 statusline 空白
    if not st:
        _snapshot_account()
        set_action("idle", "尚未运行 sc；用 /sc status 或 /sc auto 初始化")
        st = read_status()
    for line in format_status_lines(st, model=model, width=width):
        print(line)
    return 0


def _pid_path() -> Path:
    return cursor_config_dir() / PID_FILE


def _read_auto_pid() -> Optional[int]:
    path = _pid_path()
    if not path.exists():
        return None
    try:
        pid = int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return None
    try:
        os.kill(pid, 0)
        return pid
    except OSError:
        path.unlink(missing_ok=True)
        return None


def _write_pid() -> None:
    cursor_config_dir().mkdir(parents=True, exist_ok=True)
    _pid_path().write_text(str(os.getpid()), encoding="utf-8")


def cmd_auto_stop() -> int:
    pid = _read_auto_pid()
    if not pid:
        write_status(auto_running=False, auto_pid=None)
        set_action("idle", "auto 未在运行")
        print("auto 未在运行")
        return 0
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as exc:
        set_action("error", f"停止失败: {exc}", last_error=str(exc))
        print(f"停止失败: {exc}")
        return 1
    _pid_path().unlink(missing_ok=True)
    write_status(auto_running=False, auto_pid=None)
    set_action("idle", f"已停止 auto pid={pid}")
    print(f"已停止 auto pid={pid}")
    return 0


def cmd_auto(*, foreground: bool = False) -> int:
    if _read_auto_pid() and not foreground:
        print(f"auto 已在运行 pid={_read_auto_pid()}；先 sc auto stop")
        return 1
    if not foreground and os.name == "nt":
        import subprocess

        creation = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        creation |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        # 保留日志，便于排查；状态主要走 sc_status.json
        log_path = cursor_config_dir() / "sc_auto.log"
        log_f = open(log_path, "a", encoding="utf-8")  # noqa: SIM115
        subprocess.Popen(
            [sys.executable, "-m", "sc", "auto", "--fg"],
            creationflags=creation,
            close_fds=True,
            stdout=log_f,
            stderr=log_f,
        )
        time.sleep(0.5)
        set_action("polling", "已后台启动 auto", auto_running=True, auto_pid=_read_auto_pid())
        print(f"已后台启动 auto → pid 见 {_pid_path()}")
        print(f"状态: {status_json_path()}  日志: {log_path}")
        return 0

    cfg = load_config()
    interval = int(cfg.get("poll_interval") or 30)
    threshold = float(cfg.get("usage_threshold") or 95.0)
    _write_pid()
    _snapshot_account()
    write_status(
        auto_running=True,
        auto_pid=os.getpid(),
        poll_interval=interval,
        usage_threshold=threshold,
        poll_n=0,
    )
    set_action("polling", f"auto 监测启动 interval={interval}s thr={threshold}%")
    print(f"auto 监测启动 interval={interval}s threshold={threshold}% auth={auth_json_path()}")
    try:
        n = 0
        while True:
            n += 1
            write_status(poll_n=n, auto_running=True, auto_pid=os.getpid())
            token = auth.access_token()
            if not token:
                set_action("switching", f"#{n} 无 Token，自动 pull…")
                print(f"#{n} 无 Token，自动 pull...")
                cmd_pull()
            else:
                try:
                    set_action("polling", f"#{n} 查询用量…")
                    usage = api.parse_usage(api.fetch_usage(token))
                    _snapshot_account(token)
                    _snapshot_usage(usage)
                    print(f"#{n} total={usage['total_pct']}%")
                    if api.is_limit_reached(usage, threshold):
                        set_action(
                            "switching",
                            f"#{n} 超阈值 total={usage['total_pct']}%，自动换号…",
                        )
                        print("超阈值，自动换号...")
                        cmd_pull()
                    else:
                        set_action(
                            "polling",
                            f"#{n} total={usage['total_pct']}% 下轮 {interval}s",
                        )
                except Exception as exc:
                    set_action("error", f"#{n} 用量失败: {exc}", last_error=str(exc))
                    print(f"#{n} 用量失败: {exc}")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("auto 已停止")
    finally:
        _pid_path().unlink(missing_ok=True)
        write_status(auto_running=False, auto_pid=None)
        set_action("idle", "auto 已停止")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sc",
        description="Cursor Agent 便携换号 (/sc)：config.json 与 auth.json 同级",
    )
    p.add_argument("command", nargs="?", default="help")
    p.add_argument("args", nargs="*")
    p.add_argument("--fg", action="store_true", help="auto 前台运行")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    args = _normalize_argv(raw)
    parser = build_parser()
    ns = parser.parse_args(args if args else ["help"])
    cmd = (ns.command or "help").lower()
    if cmd in ("help", "-h", "--help"):
        print(
            "用法: sc|/sc <命令>\n"
            "  pull          拉号并写入 auth.json（热生效）\n"
            "  usage         查询当前用量\n"
            "  token         查看本地 Token\n"
            "  status        配置/进程/实时状态\n"
            "  statusline    供 Agent statusLine 调用（stdin JSON）\n"
            "  addkey <key>  添加 Star Cursor API Key\n"
            "  auto          后台实时轮询，超限自动换号\n"
            "  auto stop     停止后台轮询\n"
            f"config: {config_json_path()}\n"
            f"auth:   {auth_json_path()}\n"
            f"status: {status_json_path()}"
        )
        return 0
    if cmd == "pull":
        return cmd_pull()
    if cmd == "usage":
        return cmd_usage()
    if cmd == "token":
        return cmd_token()
    if cmd == "status":
        return cmd_status()
    if cmd == "statusline":
        return cmd_statusline()
    if cmd == "addkey":
        if not ns.args:
            print("用法: sc addkey <sc_xxx>")
            return 1
        return cmd_addkey(ns.args[0])
    if cmd == "auto":
        if ns.args and ns.args[0].lower() == "stop":
            return cmd_auto_stop()
        return cmd_auto(foreground=bool(ns.fg))
    print(f"未知命令: {cmd}；sc help")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
