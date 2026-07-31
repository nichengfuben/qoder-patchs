from __future__ import annotations

"""`/sc` 便携命令：拉号 / 用量 / 后台轮询换号。"""

import argparse
import os
import signal
import sys
import time
from pathlib import Path
from typing import List, Optional

from sc import api, auth
from sc.config import load_config, save_config
from sc.paths import auth_json_path, config_json_path, cursor_config_dir

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


def cmd_pull() -> int:
    cfg = load_config()
    keys = list(cfg.get("api_keys") or [])
    if not keys:
        print("无 API Key。请先: sc addkey <sc_xxx> 或编辑", config_json_path())
        return 1
    threshold = float(cfg.get("usage_threshold") or 95.0)
    retries = int(cfg.get("max_retry_per_pull") or 3)
    timeout = float(cfg.get("request_timeout") or 20)
    base = str(cfg.get("base_url") or "")
    for attempt in range(1, retries + 1):
        key = keys[(attempt - 1) % len(keys)]
        print(f"[{attempt}/{retries}] pull via {_mask(key)} ...")
        try:
            data = api.pull_token(base, key, timeout=timeout)
        except Exception as exc:
            print(f"pull 失败: {exc}")
            continue
        access, refresh, email, card = api.extract_tokens(data)
        if not access:
            print("响应无 access_token")
            continue
        if not auth.write_auth(access, refresh):
            print("写入 auth.json 失败:", auth_json_path())
            return 1
        print(f"已写入 {auth_json_path()} email={email} card={card}")
        print("(已打 cursor-agent 热更新补丁时无需重启)")
        try:
            usage = api.parse_usage(api.fetch_usage(access, timeout=timeout))
            print(f"用量 total={usage['total_pct']}%")
            if not api.is_limit_reached(usage, threshold):
                return 0
            print(f"超阈值 (>={threshold}%)，继续拉号...")
        except Exception as exc:
            print(f"用量查询失败(仍保留本次 token): {exc}")
            return 0
    return 1


def cmd_usage() -> int:
    token = auth.access_token()
    if not token:
        print("本地无 Token，先 sc pull")
        return 1
    try:
        usage = api.parse_usage(api.fetch_usage(token))
    except Exception as exc:
        print(f"查询失败: {exc}")
        return 1
    print(f"auth: {auth_json_path()}")
    print(f"total={usage['total_pct']}% auto={usage['auto_pct']}% api={usage['api_pct']}%")
    return 0


def cmd_token() -> int:
    token = auth.access_token()
    path = auth_json_path()
    if not token:
        print(f"未找到 Token ({path})")
        return 1
    uid = api.extract_user_id(token)
    print(f"path={path}\nuid={uid or '-'}\ntoken={_mask(token)}")
    return 0


def cmd_addkey(key: str) -> int:
    cfg = load_config()
    keys = list(cfg.get("api_keys") or [])
    if key in keys:
        print("Key 已存在")
        return 0
    keys.append(key)
    cfg["api_keys"] = keys
    save_config(cfg)
    print(f"已添加 {_mask(key)} → {config_json_path()}")
    return 0


def cmd_status() -> int:
    cfg = load_config()
    keys = cfg.get("api_keys") or []
    print(f"config: {config_json_path()}")
    print(f"auth:   {auth_json_path()}")
    print(f"keys:   {len(keys)}")
    for k in keys:
        print(f"  - {_mask(str(k))}")
    print(f"poll={cfg.get('poll_interval')}s threshold={cfg.get('usage_threshold')}%")
    auto_pid = _read_auto_pid()
    if auto_pid:
        print(f"auto:   running pid={auto_pid}")
    else:
        print("auto:   stopped")
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
        print("auto 未在运行")
        return 0
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as exc:
        print(f"停止失败: {exc}")
        return 1
    _pid_path().unlink(missing_ok=True)
    print(f"已停止 auto pid={pid}")
    return 0


def cmd_auto(*, foreground: bool = False) -> int:
    if _read_auto_pid() and not foreground:
        print(f"auto 已在运行 pid={_read_auto_pid()}；先 sc auto stop")
        return 1
    if not foreground and os.name == "nt":
        # 后台：再起一个分离进程
        import subprocess

        creation = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        creation |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        subprocess.Popen(
            [sys.executable, "-m", "sc", "auto", "--fg"],
            creationflags=creation,
            close_fds=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.5)
        print(f"已后台启动 auto → pid 见 {_pid_path()}")
        return 0

    cfg = load_config()
    interval = int(cfg.get("poll_interval") or 30)
    threshold = float(cfg.get("usage_threshold") or 95.0)
    _write_pid()
    print(f"auto 监测启动 interval={interval}s threshold={threshold}% auth={auth_json_path()}")
    try:
        n = 0
        while True:
            n += 1
            token = auth.access_token()
            if not token:
                print(f"#{n} 无 Token，自动 pull...")
                cmd_pull()
            else:
                try:
                    usage = api.parse_usage(api.fetch_usage(token))
                    print(f"#{n} total={usage['total_pct']}%")
                    if api.is_limit_reached(usage, threshold):
                        print("超阈值，自动换号...")
                        cmd_pull()
                except Exception as exc:
                    print(f"#{n} 用量失败: {exc}")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("auto 已停止")
    finally:
        _pid_path().unlink(missing_ok=True)
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
            "  status        配置/进程状态\n"
            "  addkey <key>  添加 Star Cursor API Key\n"
            "  auto          后台实时轮询，超限自动换号\n"
            "  auto stop     停止后台轮询\n"
            f"config: {config_json_path()}\n"
            f"auth:   {auth_json_path()}"
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
