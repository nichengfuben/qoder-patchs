from __future__ import annotations

"""`/sc` 便携命令入口（薄层：解析 + 分发）。"""

import argparse
import sys
from typing import List, Optional

from sc.core.paths import auth_json_path, config_json_path
from sc.encoding import ensure_utf8_stdio
from sc.run import instances as inst
from sc.run.auto import cmd_auto, cmd_auto_stop
from sc.run.commands import (
    cmd_addkey,
    cmd_doctor,
    cmd_pull,
    cmd_status,
    cmd_statusline,
    cmd_token,
    cmd_usage,
)
from sc.run.status_store import status_json_path


def _normalize_argv(argv: List[str]) -> List[str]:
    out = list(argv)
    while out and out[0] in ("/sc", "sc"):
        out = out[1:]
    if out and out[0].startswith("/") and out[0] != "/":
        out[0] = out[0][1:]
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sc",
        description="Cursor Agent 便携换号：多实例心跳 + 单 leader auto",
    )
    p.add_argument("command", nargs="?", default="help")
    p.add_argument("args", nargs="*")
    p.add_argument("--fg", action="store_true", help="auto 前台运行")
    p.add_argument("--parent", type=int, default=None, help="父进程 pid；退出后本实例自动下线")
    return p


def _print_help() -> None:
    print(
        "用法: sc <命令>\n"
        "  auto / auto stop   保活；仅最晚 leader 跑 auto，丢 leader 立即停\n"
        "  status             配置/实例/用量\n"
        "  statusline         Agent statusLine\n"
        "  pull / usage       手动拉号 / 手动刷新用量（调试）\n"
        "  token / addkey    Token / API Key\n"
        "  doctor             自检 hot-auth 补丁与 Bearer sub 对照\n"
        f"config:     {config_json_path()}\n"
        f"auth:       {auth_json_path()}\n"
        f"status:     {status_json_path()}\n"
        f"instances:  {inst.instances_json_path()}"
    )


def main(argv: Optional[List[str]] = None) -> int:
    ensure_utf8_stdio()
    raw = list(sys.argv[1:] if argv is None else argv)
    args = _normalize_argv(raw)
    ns = build_parser().parse_args(args if args else ["help"])
    cmd = (ns.command or "help").lower()
    dispatch = {
        "help": lambda: (_print_help(), 0)[1],
        "-h": lambda: (_print_help(), 0)[1],
        "--help": lambda: (_print_help(), 0)[1],
        "pull": cmd_pull,
        "usage": cmd_usage,
        "token": cmd_token,
        "doctor": cmd_doctor,
        "status": cmd_status,
        "statusline": cmd_statusline,
    }
    if cmd in dispatch:
        return dispatch[cmd]() if cmd in ("help", "-h", "--help") else dispatch[cmd]()
    if cmd == "addkey":
        if not ns.args:
            print("用法: sc addkey <sc_xxx>")
            return 1
        return cmd_addkey(ns.args[0])
    if cmd == "auto":
        if ns.args and ns.args[0].lower() == "stop":
            return cmd_auto_stop()
        return cmd_auto(foreground=bool(ns.fg), parent_pid=ns.parent)
    print(f"未知命令: {cmd}；sc help")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
