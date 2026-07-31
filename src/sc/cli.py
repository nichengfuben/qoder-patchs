from __future__ import annotations

"""`/sc` 便携命令：拉号 / 用量 / 多实例心跳单 leader auto + statusline。"""

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import List, Optional

from sc.encoding import ensure_utf8_stdio, utf8_env
from sc import api, auth, instances as inst
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
    # 无 email 时用短 uid，避免 statusline 长期显示 -/free
    show_email = email.strip() if email else ""
    if not show_email and uid:
        show_email = uid[:12] + ("..." if len(uid) > 12 else "")
    doc = inst.read_instances()
    write_status(
        email=show_email or None,
        card=card or None,
        uid=uid or None,
        keys=len(cfg.get("api_keys") or []),
        poll_interval=cfg.get("poll_interval"),
        usage_threshold=cfg.get("usage_threshold"),
        auto_running=bool(doc.get("leader_id")),
        auto_pid=os.getpid() if doc.get("leader_id") else None,
        auth_path=str(auth_json_path()),
        config_path=str(config_json_path()),
        status_path=str(status_json_path()),
        instance_count=inst.online_count(doc),
        leader_id=doc.get("leader_id"),
    )


def _snapshot_usage(usage: dict) -> None:
    cur = read_status()
    try:
        seq = int(cur.get("usage_seq") or 0) + 1
    except Exception:
        seq = 1
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
        usage_seq=seq,
        usage_at=time.strftime("%H:%M:%S"),
        usage_fetched_at=time.time(),
    )
    # publish 时带上 included/bonus/is_unlimited，statusline 读 json 即可完整还原
    inst.publish_usage(
        {
            "total_pct": usage.get("total_pct"),
            "auto_pct": usage.get("auto_pct"),
            "api_pct": usage.get("api_pct"),
            "plan_status": usage.get("status"),
            "membership": usage.get("membership"),
            "used": usage.get("used"),
            "remaining": usage.get("remaining"),
            "total": usage.get("total"),
            "included": usage.get("included"),
            "bonus": usage.get("bonus"),
            "is_unlimited": usage.get("is_unlimited"),
            "usage_seq": seq,
        }
    )


def _switch_threshold(cfg: dict) -> float:
    """优先 ``switch_threshold``（对齐 client），否则 ``usage_threshold``。"""
    if cfg.get("switch_threshold") is not None:
        return float(cfg.get("switch_threshold"))
    return float(cfg.get("usage_threshold") or 95.0)


def cmd_pull() -> int:
    cfg = load_config()
    keys = list(cfg.get("api_keys") or [])
    if not keys:
        set_action("error", "无 API Key", last_error="missing api key")
        print("无 API Key。请先: sc addkey <sc_xxx> 或编辑", config_json_path())
        return 1
    threshold = _switch_threshold(cfg)
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
            hint = api.short_error(exc)
            # 瞬时网络/SSL：不刷 ERR 到 statusbar，静默重试
            if api.is_transient_net_error(exc) or hint in (
                "SSL断连",
                "SSL失败",
                "超时",
                "网络错误",
                "连接重置",
                "DNS失败",
            ):
                print(f"pull 暂不可用: {hint}")
            else:
                # HTTP 404 等：保留 PULL 态短提示，最终 retries 再定论
                print(f"pull 失败: {hint}")
            continue
        access, refresh, email, card = api.extract_tokens(data)
        if not access:
            print("响应无 access_token")
            continue
        if not auth.write_auth(access, refresh):
            set_action("error", "写入 auth.json 失败", last_error="write auth failed")
            print("写入 auth.json 失败:", auth_json_path())
            return 1
        _snapshot_account(access, email=email, card=card)
        write_status(last_pull_at=time.strftime("%Y-%m-%d %H:%M:%S"), last_error="")
        print(f"已写入 {auth_json_path()} email={email or '-'} card={card or '-'}")
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
        except Exception:
            # 用量失败不改 statusbar：token 已写入，等下次成功再渲染
            set_action("ok", "pull 成功")
            return 0
    set_action("error", "pull 重试耗尽", last_error="retries exhausted")
    return 1


def cmd_usage() -> int:
    """手动刷新用量（调试用）。"""
    token = auth.access_token()
    if not token:
        set_action("error", "未找到 Token", last_error="no token")
        print(f"未找到 Token ({auth_json_path()})")
        return 1
    try:
        usage = api.parse_usage(api.fetch_usage(token))
    except Exception as exc:
        hint = api.short_error(exc)
        print(f"用量查询失败: {hint}")
        return 1
    _snapshot_account(token)
    _snapshot_usage(usage)
    write_status(last_error="")
    set_action("ok", f"usage total={usage['total_pct']}%")
    print(
        f"total={usage['total_pct']}%  auto={usage['auto_pct']}%  "
        f"api={usage['api_pct']}%  status={usage['status']}  "
        f"membership={usage.get('membership')}"
    )
    print(f"used={usage.get('used')} remaining={usage.get('remaining')} "
          f"pool={usage.get('total')}")
    if usage.get("message"):
        print(usage["message"])
    for line in format_status_lines():
        print("--- live ---")
        print(line)
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
    doc = inst.read_instances()
    leader = doc.get("leader_id")
    n_online = inst.online_count(doc)
    _snapshot_account()
    write_status(
        auto_running=bool(leader),
        keys=len(keys),
        instance_count=n_online,
        leader_id=leader,
    )
    token = auth.access_token()
    if token:
        try:
            usage = api.parse_usage(api.fetch_usage(token))
            _snapshot_usage(usage)
            set_action(
                "ok" if not leader else "polling",
                f"status total={usage['total_pct']}%",
            )
        except Exception:
            pass
    else:
        set_action("idle", "无 Token")

    print(f"config: {config_json_path()}")
    print(f"auth:   {auth_json_path()}")
    print(f"status: {status_json_path()}")
    print(f"instances: {inst.instances_json_path()}")
    print(f"keys:   {len(keys)}")
    for k in keys:
        print(f"  - {_mask(k)}")
    print(f"poll={cfg.get('poll_interval')}s threshold={_switch_threshold(cfg)}%")
    print(f"online: {n_online}  leader={leader or '-'}")
    for iid, info in (doc.get("instances") or {}).items():
        if not isinstance(info, dict):
            continue
        print(
            f"  - {iid[:8]}… role={info.get('role')} pid={info.get('pid')} "
            f"hb={info.get('heartbeat_at')}"
        )
    if leader:
        print("auto:   leader running")
    else:
        print("auto:   no leader (启动 sc auto / agent)")
    for line in format_status_lines():
        print("--- live ---")
        print(line)
    return 0


def _apply_shared_usage(doc: dict) -> bool:
    """从 ``sc_instances.json`` 的 usage 合并进 ``sc_status.json``（只读共享、写本地条）。

    leader auto 实时写 instances；leader/非 leader 的 statusline 都走这里读。
    """
    shared = doc.get("usage") if isinstance(doc, dict) else None
    if not isinstance(shared, dict) or not shared:
        return False
    cur_leader = doc.get("leader_id")
    if shared.get("leader_id") and cur_leader and shared.get("leader_id") != cur_leader:
        return False
    published = float(shared.get("published_at") or 0)
    if published <= 0:
        return False
    if cur_leader:
        info = (doc.get("instances") or {}).get(cur_leader)
        hb = float(info.get("heartbeat_at") or 0) if isinstance(info, dict) else 0.0
        if inst._is_stale(hb):  # noqa: SLF001
            return False
    cur = read_status()
    local = float(cur.get("usage_fetched_at") or 0)
    if published < local and cur.get("total_pct") is not None:
        return False
    write_status(
        total_pct=shared.get("total_pct"),
        auto_pct=shared.get("auto_pct"),
        api_pct=shared.get("api_pct"),
        plan_status=shared.get("plan_status"),
        membership=shared.get("membership"),
        used=shared.get("used"),
        remaining=shared.get("remaining"),
        total_tokens=shared.get("total"),
        included=shared.get("included"),
        bonus=shared.get("bonus"),
        is_unlimited=shared.get("is_unlimited"),
        usage_seq=shared.get("usage_seq"),
        usage_fetched_at=published,
        last_error="",
        leader_id=cur_leader,
        auto_running=bool(cur_leader),
    )
    return True


def _sync_leader_to_status(doc: dict) -> None:
    """按 instances 同步 / 清空 sc_status 中的 leader 字段。"""
    leader = doc.get("leader_id")
    n_online = inst.online_count(doc)
    if not leader or inst._is_stale(inst.leader_heartbeat_at(doc)):  # noqa: SLF001
        write_status(
            leader_id=None,
            auto_running=False,
            auto_pid=None,
            instance_count=n_online,
        )
        return
    write_status(
        leader_id=leader,
        auto_running=True,
        instance_count=n_online,
        leader_heartbeat_at=inst.leader_heartbeat_at(doc),
    )


def _refresh_usage_for_display(*, timeout: float = 8.0) -> bool:
    """冷启动无 json 用量时补拉一次（不换号）。"""
    token = auth.access_token()
    if not token:
        return False
    try:
        usage = api.parse_usage(api.fetch_usage(token, timeout=timeout))
    except Exception:
        return False
    _snapshot_account(token)
    _snapshot_usage(usage)
    write_status(last_error="")
    set_action("ok", f"usage total={usage['total_pct']}%")
    return True


def cmd_statusline() -> int:
    """statusLine：委托极速只读入口（见 ``sc.statusline_fast``）。"""
    from sc.statusline_fast import run

    return run()


def _statusline_display_state() -> dict:
    """兼容旧调用；实际逻辑在 ``statusline_fast.display_state``。"""
    from sc.statusline_fast import display_state

    return display_state()


def _pid_path() -> Path:
    return cursor_config_dir() / PID_FILE


def _pid_alive(pid: int) -> bool:
    return inst._pid_alive(pid)  # noqa: SLF001 — 共用探测


def _read_auto_pid() -> Optional[int]:
    path = _pid_path()
    if not path.exists():
        return None
    try:
        pid = int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return None
    if _pid_alive(pid):
        return pid
    path.unlink(missing_ok=True)
    return None


def _write_pid() -> None:
    cursor_config_dir().mkdir(parents=True, exist_ok=True)
    _pid_path().write_text(str(os.getpid()), encoding="utf-8")


def _kill_legacy_exclusive_auto() -> None:
    """清理旧版独占 sc_auto.pid 守护（未登记到 instances 的）。"""
    pid = _read_auto_pid()
    if not pid or pid == os.getpid():
        return
    doc = inst.read_instances()
    known = {
        int(info.get("pid") or 0)
        for info in (doc.get("instances") or {}).values()
        if isinstance(info, dict)
    }
    if pid in known:
        return
    try:
        if os.name == "nt":
            import ctypes

            h = ctypes.windll.kernel32.OpenProcess(0x0001, False, int(pid))
            if h:
                ctypes.windll.kernel32.TerminateProcess(h, 1)
                ctypes.windll.kernel32.CloseHandle(h)
        else:
            os.kill(pid, signal.SIGTERM)
    except Exception:
        pass
    _pid_path().unlink(missing_ok=True)


def cmd_auto_stop() -> int:
    killed = inst.stop_all_instances()
    _pid_path().unlink(missing_ok=True)
    write_status(auto_running=False, auto_pid=None, leader_id=None, instance_count=0)
    set_action("idle", "已停止全部 auto 实例")
    print(f"已停止实例 pids={killed or '-'}")
    return 0


def _still_leader(instance_id: str) -> bool:
    """快速复核：仍是当前 leader 才允许继续 auto。"""
    try:
        return inst.is_leader(instance_id)
    except Exception:
        return False


def _leader_tick(
    instance_id: str,
    n: int,
    interval: int,
    threshold: float,
) -> None:
    """仅 leader 执行：查用量 / 必要时换号；中途丢 leader 立即停。"""
    if not _still_leader(instance_id):
        print(f"#{n} 已非 leader，跳过 auto tick")
        return
    token = auth.access_token()
    if not token:
        if not _still_leader(instance_id):
            return
        set_action("switching", f"#{n} 无 Token，自动 pull…")
        print(f"#{n} 无 Token，自动 pull...")
        if _still_leader(instance_id):
            cmd_pull()
        return
    try:
        if not _still_leader(instance_id):
            print(f"#{n} 拉取前失去 leader，立即停")
            return
        usage = api.parse_usage(api.fetch_usage(token))
        if not _still_leader(instance_id):
            print(f"#{n} 拉取后失去 leader，丢弃结果并立即停")
            return
        _snapshot_account(token)
        _snapshot_usage(usage)
        write_status(poll_n=n, last_error="")
        print(f"#{n} total={usage['total_pct']}%")
        if api.is_limit_reached(usage, threshold):
            if not _still_leader(instance_id):
                print(f"#{n} 换号前失去 leader，立即停")
                return
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
    except Exception:
        pass


def cmd_auto(*, foreground: bool = False, parent_pid: Optional[int] = None) -> int:
    """多实例保活：最晚上线者为 leader；**仅 leader 跑 auto**；丢 leader 立即停 auto。"""
    if not foreground and os.name == "nt":
        import subprocess

        creation = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        creation |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        log_path = cursor_config_dir() / "sc_auto.log"
        log_f = open(log_path, "a", encoding="utf-8")  # noqa: SIM115
        # 注意：cursor-agent.cmd 的 start /B 会立刻退出，不能绑 cmd pid。
        # 无 --parent 时实例常驻，靠心跳+进程存活判定；sc auto stop 可清。
        args = [sys.executable, "-X", "utf8", "-m", "sc", "auto", "--fg"]
        if parent_pid:
            args.extend(["--parent", str(parent_pid)])
        subprocess.Popen(
            args,
            creationflags=creation,
            close_fds=True,
            stdout=log_f,
            stderr=log_f,
            env=utf8_env(),
        )
        time.sleep(0.4)
        print(f"已后台启动实例 → {inst.instances_json_path()}")
        print(f"状态: {status_json_path()}  日志: {log_path}")
        return 0

    _kill_legacy_exclusive_auto()
    cfg = load_config()
    interval = max(1, int(cfg.get("poll_interval") or 5))
    threshold = _switch_threshold(cfg)
    iid = inst.register_instance(parent_pid=parent_pid)
    _write_pid()
    _snapshot_account()
    write_status(
        poll_interval=interval,
        usage_threshold=threshold,
        poll_n=0,
        instance_id=iid,
    )
    print(
        f"instance={iid} parent={parent_pid or '-'} "
        f"interval={interval}s thr={threshold}% file={inst.instances_json_path()}"
    )
    last_poll = 0.0
    poll_n = 0
    was_leader = False
    try:
        while True:
            if parent_pid and not _pid_alive(parent_pid):
                print("parent 已退出，实例下线")
                break
            doc = inst.heartbeat(iid, parent_pid=parent_pid)
            if iid not in (doc.get("instances") or {}):
                print("实例已被清理（parent 退出或冲突），结束")
                break

            leader_now = inst.is_leader(iid, doc)
            # 仅 leader：扫全部时间戳清理 + 跑 auto
            if leader_now:
                doc = inst.leader_prune_stale(iid)
                leader_now = inst.is_leader(iid, doc)
            else:
                # 非 leader：leader 心跳 >=10s → 清掉该实例和 Leader
                prev_leader = doc.get("leader_id")
                doc = inst.follower_clear_stale_leader(iid)
                if prev_leader and doc.get("leader_id") != prev_leader:
                    print(
                        f"follower 清过期 leader={prev_leader} "
                        f"→ new={doc.get('leader_id') or '-'}"
                    )
                leader_now = inst.is_leader(iid, doc)

            n_online = inst.online_count(doc)

            if leader_now:
                if not was_leader:
                    set_action("polling", f"成为 leader，开始 auto x{n_online}")
                    print(f"leader acquired → 开始 auto online={n_online}")
                    was_leader = True
                    last_poll = 0.0  # 立刻跑一轮
                write_status(
                    instance_count=n_online,
                    leader_id=doc.get("leader_id"),
                    auto_running=True,
                    auto_pid=os.getpid(),
                    instance_id=iid,
                )
                now = time.time()
                if now - last_poll >= interval:
                    # 开跑前再确认一次，防止刚被更晚上线者顶掉
                    if not _still_leader(iid):
                        print("leader 变更，立即停止 auto")
                        was_leader = False
                        write_status(auto_running=False, auto_pid=None)
                        set_action("ok", f"follower 监听 x{n_online}")
                    else:
                        poll_n += 1
                        last_poll = now
                        _leader_tick(iid, poll_n, interval, threshold)
                        if not _still_leader(iid):
                            print("leader 变更，auto tick 后立即停止")
                            was_leader = False
                            write_status(auto_running=False, auto_pid=None)
                            set_action("ok", f"follower 监听 x{inst.online_count()}")
            else:
                if was_leader:
                    # 丢 leader：立即停 auto（不再 poll / pull）
                    print("leader 变更，立即停止 auto → follower")
                    was_leader = False
                    last_poll = 0.0
                    write_status(
                        instance_count=n_online,
                        leader_id=doc.get("leader_id"),
                        auto_running=False,
                        auto_pid=None,
                        instance_id=iid,
                    )
                    set_action("ok", f"follower 监听 x{n_online}")
                else:
                    write_status(
                        instance_count=n_online,
                        leader_id=doc.get("leader_id"),
                        auto_running=False,
                        auto_pid=None,
                        instance_id=iid,
                    )
                    _apply_shared_usage(doc)
                    set_action("ok", f"follower 监听 x{n_online}")
            time.sleep(inst.HEARTBEAT_SEC)
    except KeyboardInterrupt:
        print("auto 已停止")
    finally:
        try:
            inst.unregister(iid)
        except Exception:
            pass
        if _read_auto_pid() == os.getpid():
            _pid_path().unlink(missing_ok=True)
        doc = inst.read_instances()
        write_status(
            auto_running=bool(doc.get("leader_id")),
            auto_pid=None,
            instance_count=inst.online_count(doc),
            leader_id=doc.get("leader_id"),
        )
        if not doc.get("leader_id"):
            set_action("idle", "auto 已停止")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sc",
        description="Cursor Agent 便携换号：多实例心跳 + 单 leader auto",
    )
    p.add_argument("command", nargs="?", default="help")
    p.add_argument("args", nargs="*")
    p.add_argument("--fg", action="store_true", help="auto 前台运行")
    p.add_argument(
        "--parent",
        type=int,
        default=None,
        help="父进程 pid；退出后本实例自动下线",
    )
    return p


def main(argv: Optional[List[str]] = None) -> int:
    ensure_utf8_stdio()
    raw = list(sys.argv[1:] if argv is None else argv)
    args = _normalize_argv(raw)
    parser = build_parser()
    ns = parser.parse_args(args if args else ["help"])
    cmd = (ns.command or "help").lower()
    if cmd in ("help", "-h", "--help"):
        print(
            "用法: sc <命令>\n"
            "  auto / auto stop   保活；仅最晚 leader 跑 auto，丢 leader 立即停\n"
            "  status             配置/实例/用量\n"
            "  statusline         Agent statusLine\n"
            "  pull / usage       手动拉号 / 手动刷新用量（调试）\n"
            "  token / addkey    Token / API Key\n"
            f"config:     {config_json_path()}\n"
            f"auth:       {auth_json_path()}\n"
            f"status:     {status_json_path()}\n"
            f"instances:  {inst.instances_json_path()}"
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
        return cmd_auto(foreground=bool(ns.fg), parent_pid=ns.parent)
    print(f"未知命令: {cmd}；sc help")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
