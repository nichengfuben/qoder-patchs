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
from sc.keys import KeyPool, KeyState
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


def _usage_threshold(cfg: dict) -> float:
    """对齐 client.py ``/auto``：只用 ``usage_threshold``（默认 95）。

    ``switch_threshold`` 仅用于 Key 日用量轮换（见 ``KeyPool``），不参与 Cursor 换号。
    """
    if cfg.get("usage_threshold") is not None:
        return float(cfg.get("usage_threshold"))
    return 95.0


def _make_pool(cfg: dict) -> KeyPool:
    keys = [str(k) for k in (cfg.get("api_keys") or []) if k]
    return KeyPool(
        keys=keys,
        threshold=int(cfg.get("switch_threshold") or 80),
        refresh_interval=int(cfg.get("status_refresh_interval") or 60),
    )


def _refresh_key_state(pool: KeyPool, s: KeyState, cfg: dict) -> bool:
    try:
        data = api.key_status(
            str(cfg.get("base_url") or ""),
            s.key,
            timeout=float(cfg.get("request_timeout") or 20),
        )
        s.name = str(data.get("name") or s.name)
        s.is_active = bool(data.get("is_active", s.is_active))
        s.daily_used = data.get("daily_used")
        s.daily_limit = data.get("daily_limit")
        s.rpm = data.get("rate_limit_per_minute")
        s.total_used = data.get("total_used")
        s.last_checked = time.time()
        s.errors = 0
        return True
    except Exception as exc:
        print(f"刷新 Key[{s.masked()}] 失败: {api.short_error(exc)}")
        s.errors += 1
        return False


def _ensure_usable_key(pool: KeyPool, cfg: dict) -> Optional[KeyState]:
    total = len(pool.all())
    if total == 0:
        return None
    for _ in range(total):
        s = pool.current
        if s is None:
            return None
        if pool.is_stale(s):
            _refresh_key_state(pool, s, cfg)
        if pool.should_switch(s):
            print(
                f"Key[{s.masked()}] daily_used={s.daily_used} "
                f">= 阈值 {pool.threshold}，切换..."
            )
            pool.switch_next()
            continue
        return s
    return None


def _acquire_token(pool: KeyPool, cfg: dict) -> Optional[dict]:
    """对齐 client.py ``_acquire_token``：Key 轮换 + HTTP 错误处理。"""
    max_retry = int(cfg.get("max_retry_per_pull") or 3)
    timeout = float(cfg.get("request_timeout") or 20)
    base = str(cfg.get("base_url") or "")
    for attempt in range(1, max_retry + 1):
        s = _ensure_usable_key(pool, cfg)
        if s is None:
            print("所有 Key 均已达阈值或不可用")
            return None
        set_action(
            "pulling",
            f"pull [{attempt}/{max_retry}] via {s.masked()}",
            last_error="",
        )
        print(f"[{attempt}/{max_retry}] pull via {s.masked()} ...")
        try:
            result = api.pull_token(base, s.key, timeout=timeout)
            if s.daily_used is not None:
                try:
                    s.daily_used = int(s.daily_used) + 1
                except Exception:
                    pass
            print(f"Token 获取成功，卡密: {result.get('card_number', '?')}")
            return result
        except api.ApiError as e:
            if e.status == 403:
                payload = e.payload
                if payload.get("error") == "Daily limit reached":
                    s.daily_used = payload.get("daily_used", s.daily_used)
                    s.daily_limit = payload.get("daily_limit", s.daily_limit)
                    s.last_checked = time.time()
                    print(
                        f"Key[{s.masked()}] 每日上限 "
                        f"({s.daily_used}/{s.daily_limit})，切换"
                    )
                else:
                    s.is_active = False
                    print(f"Key[{s.masked()}] 已被禁用")
                pool.switch_next()
            elif e.status == 429:
                wait = float(e.payload.get("retry_after") or 5)
                print(f"速率限制，等待 {wait}s")
                time.sleep(wait)
            elif e.status == 503:
                print("账号池无可用卡密，3s 后重试")
                time.sleep(3)
            elif e.status == 500:
                print("卡密尝试全部失败，切换 Key")
                pool.switch_next()
            elif e.status == 401:
                s.is_active = False
                print(f"Key[{s.masked()}] 无效，剔除并切换")
                pool.switch_next()
            else:
                print(f"未知错误 HTTP {e.status}")
                time.sleep(2)
        except Exception as exc:
            hint = api.short_error(exc)
            if api.is_transient_net_error(exc) or hint in (
                "SSL断连",
                "SSL失败",
                "超时",
                "网络错误",
                "连接重置",
                "DNS失败",
            ):
                print(f"pull 暂不可用: {hint}，2s 后重试")
            else:
                print(f"pull 失败: {hint}")
            time.sleep(2)
    print(f"已重试 {max_retry} 次，未能获取 Token")
    return None


def _do_pull_and_write(pool: KeyPool, cfg: dict) -> bool:
    """对齐 client.py ``_do_pull_and_write``：拉一次并写 auth.json。"""
    if pool.is_empty():
        set_action("error", "无 API Key", last_error="missing api key")
        print("无 API Key。请先: sc addkey <sc_xxx> 或编辑", config_json_path())
        return False
    result = _acquire_token(pool, cfg)
    if not result:
        return False
    access, refresh, email, card = api.extract_tokens(result)
    if not access:
        print("pull-token 返回里没有 access_token")
        return False
    if not auth.write_auth(access, refresh):
        set_action("error", "写入 auth.json 失败", last_error="write auth failed")
        print("写入 auth.json 失败:", auth_json_path())
        return False
    _snapshot_account(access, email=email, card=card)
    write_status(last_pull_at=time.strftime("%Y-%m-%d %H:%M:%S"), last_error="")
    print(f"已写入 {auth_json_path()} email={email or '-'} card={card or '-'}")
    print(f"uid={api.extract_user_id(access) or '-'}")
    print("(已打 cursor-agent 热更新补丁时无需重启)")
    return True


def _pull_until_acceptable_usage(
    pool: KeyPool,
    cfg: dict,
    threshold: float,
    *,
    max_attempts: Optional[int] = None,
    title_prefix: str = "新号用量",
) -> bool:
    """对齐 client.py：拉号后立刻查用量；仍超阈值则马上再拉。"""
    attempts = (
        max_attempts
        if max_attempts is not None
        else int(cfg.get("max_retry_per_pull") or 3)
    )
    timeout = float(cfg.get("request_timeout") or 20)
    for attempt in range(1, attempts + 1):
        if not _do_pull_and_write(pool, cfg):
            print(
                f"换号失败 ({attempt}/{attempts})"
                if attempt > 1
                else "自动换号失败"
            )
            return False
        at = auth.access_token()
        if not at:
            print("换号后无法读取本地 Token")
            return False
        try:
            print(f"校验用量 [{attempt}/{attempts}]...")
            usage = api.parse_usage(api.fetch_usage(at, timeout=timeout))
            _snapshot_account(at)
            _snapshot_usage(usage)
            print(
                f"{title_prefix} #{attempt}/{attempts} "
                f"total={usage['total_pct']:.1f}% "
                f"auto={usage['auto_pct']:.1f}% api={usage['api_pct']:.1f}%"
            )
            if not api.is_limit_reached(usage, threshold):
                set_action(
                    "ok",
                    f"换号成功 total={usage['total_pct']:.1f}% < {threshold}%",
                )
                print(
                    f"换号成功，额度正常 "
                    f"({usage['total_pct']:.1f}% < {threshold}%)"
                )
                return True
            if attempt < attempts:
                set_action(
                    "switching",
                    f"新号仍超阈值 (>={threshold}%)，继续拉号",
                )
                print(
                    f"新号仍超阈值 ({usage['total_pct']:.1f}% >= {threshold}%)，"
                    f"立即再次换号..."
                )
            else:
                set_action(
                    "error",
                    f"连续换号 {attempts} 次仍超阈值",
                    last_error="still over threshold",
                )
                print(
                    f"已连续换号 {attempts} 次仍超阈值 "
                    f"({usage['total_pct']:.1f}% >= {threshold}%)"
                )
        except Exception as exc:
            hint = api.short_error(exc)
            print(f"校验新号用量失败: {hint}")
            # 对齐 client：校验失败视为本轮失败（token 已写入，下轮 auto 再查）
            set_action("ok", f"pull 已写入，用量校验失败: {hint}")
            return False
    return False


def cmd_pull() -> int:
    """对齐 client.py ``/pull``：拉号直到用量低于 ``usage_threshold``。"""
    cfg = load_config()
    pool = _make_pool(cfg)
    threshold = _usage_threshold(cfg)
    _snapshot_account()
    ok = _pull_until_acceptable_usage(
        pool, cfg, threshold, title_prefix="拉号后用量"
    )
    return 0 if ok else 1


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


def cmd_doctor() -> int:
    """自检：hot-auth 补丁标记、auth.json sub、agentcli-last-bearer 对照。"""
    from patches.cursor_agent import (
        DISK_MARKER,
        EPHEMERAL_NULL_MARKER,
        MARKER,
        CursorAgentPatch,
    )
    from sc.paths import find_cursor_agent_bundle

    ok = True
    bundle = find_cursor_agent_bundle()
    print(f"bundle: {bundle or '(missing)'}")
    if bundle is None:
        print("FAIL: 未找到 cursor-agent versions/*/index.js")
        return 1

    patch = CursorAgentPatch()
    status = patch.check(bundle)
    print(f"patch:  {status}")
    index = bundle / "index.js"
    text = index.read_text(encoding="utf-8", errors="ignore")
    checks = {
        "hot-auth marker": MARKER in text,
        "ephemeral null": EPHEMERAL_NULL_MARKER in text,
        "disk bearer": DISK_MARKER in text,
        "no ephemeralToken:R": "ephemeralToken:R," not in text,
        "no cache early-return": "if(this.cachedAccessToken)return this.cachedAccessToken" not in text,
    }
    for name, good in checks.items():
        print(f"  {'OK' if good else 'FAIL'}: {name}")
        ok = ok and good

    auth_path = auth_json_path()
    sub = auth.token_subject()
    print(f"auth:   {auth_path}")
    print(f"auth.sub: {sub or '(none)'}")
    if not sub:
        print("FAIL: auth.json 无可用 accessToken")
        ok = False

    bearer_path = cursor_config_dir() / "agentcli-last-bearer.json"
    print(f"bearer: {bearer_path}")
    if bearer_path.is_file():
        try:
            doc = json.loads(bearer_path.read_text(encoding="utf-8"))
            bsub = doc.get("sub")
            print(
                f"bearer.sub: {bsub}  ts={doc.get('ts')} "
                f"pid={doc.get('pid')} via={doc.get('via')}"
            )
            if sub and bsub and sub != bsub:
                print("FAIL: auth.sub ≠ bearer.sub — Agent 可能未重启或仍用旧进程")
                ok = False
            elif sub and bsub and sub == bsub:
                print("OK: auth.sub == bearer.sub")
        except Exception as exc:
            print(f"FAIL: 无法解析 last-bearer: {exc}")
            ok = False
    else:
        print("WARN: 尚无 agentcli-last-bearer.json（重启 ag 并发一条消息后生成）")

    ps1 = Path(os.environ.get("LOCALAPPDATA", "")) / "cursor-agent" / "cursor-agent.ps1"
    if ps1.is_file():
        ps = ps1.read_text(encoding="utf-8", errors="ignore")
        cache_off = "disable NODE_COMPILE_CACHE" in ps
        print(f"  {'OK' if cache_off else 'FAIL'}: NODE_COMPILE_CACHE disabled in cursor-agent.ps1")
        ok = ok and cache_off

    print("doctor: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


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
    sub = auth.token_subject(token)
    if token:
        print(f"token:  present len={len(token)} sub={sub or '?'}")
    else:
        print("token:  missing")
    print(f"keys:   {len(keys)}")
    for k in keys:
        print(f"  - {_mask(k)}")
    print(f"poll={cfg.get('poll_interval')}s threshold={_usage_threshold(cfg)}%")
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
    pool: KeyPool,
    cfg: dict,
) -> None:
    """对齐 client.py ``_cmd_auto`` 单轮：查用量 / 超阈值则 pull_until_acceptable。

    多实例约束：中途丢 leader 立即停。
    """
    if not _still_leader(instance_id):
        print(f"#{n} 已非 leader，跳过 auto tick")
        return

    token = auth.access_token()
    if not token:
        if not _still_leader(instance_id):
            return
        set_action("switching", f"#{n} 无 Token，自动拉号…")
        print(f"#{n} 无 Token，自动拉号...")
        if not _still_leader(instance_id):
            return
        ok = _do_pull_and_write(pool, cfg)
        if not ok:
            print(f"#{n} 拉号失败，{interval}s 后重试")
            set_action("error", f"#{n} 拉号失败", last_error="pull failed")
            return
        token = auth.access_token()
        if not token:
            return

    try:
        if not _still_leader(instance_id):
            print(f"#{n} 查询前失去 leader，立即停")
            return
        print(f"#{n} 查询用量...")
        usage = api.parse_usage(
            api.fetch_usage(token, timeout=float(cfg.get("request_timeout") or 20))
        )
        if not _still_leader(instance_id):
            print(f"#{n} 查询后失去 leader，丢弃结果并立即停")
            return
        _snapshot_account(token)
        _snapshot_usage(usage)
        write_status(poll_n=n, last_error="")
        print(
            f"#{n} total={usage['total_pct']:.1f}% "
            f"auto={usage['auto_pct']:.1f}% api={usage['api_pct']:.1f}% "
            f"status={usage.get('status')}"
        )
        if api.is_limit_reached(usage, threshold):
            if not _still_leader(instance_id):
                print(f"#{n} 换号前失去 leader，立即停")
                return
            set_action(
                "switching",
                f"#{n} 超阈值 total={usage['total_pct']:.1f}% >= {threshold}%",
            )
            print(
                f"达到阈值 (total={usage['total_pct']:.1f}% >= {threshold}%)，"
                f"自动换号..."
            )
            if not _pull_until_acceptable_usage(
                pool, cfg, threshold, title_prefix=f"监测#{n}换号"
            ):
                print(f"#{n} 自动换号未获得可用额度，下轮重试")
                set_action(
                    "error",
                    f"#{n} 换号未获可用额度",
                    last_error="switch failed",
                )
        else:
            set_action(
                "polling",
                f"#{n} total={usage['total_pct']:.1f}% < {threshold}% 下轮 {interval}s",
            )
            print(f"额度正常 ({usage['total_pct']:.1f}% < {threshold}%)")
    except Exception as exc:
        hint = api.short_error(exc)
        print(f"#{n} 查询用量失败: {hint}")
        # 瞬时网络不刷 ERR；其它错误短提示，保留上次用量快照
        if not (
            api.is_transient_net_error(exc)
            or hint
            in ("SSL断连", "SSL失败", "超时", "网络错误", "连接重置", "DNS失败")
        ):
            set_action("polling", f"#{n} 用量查询失败: {hint}", last_error=hint)


def cmd_auto(*, foreground: bool = False, parent_pid: Optional[int] = None) -> int:
    """多实例保活：最晚上线者为 leader；**仅 leader 跑 auto**（对齐 client ``/auto``）。"""
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
    threshold = _usage_threshold(cfg)
    pool = _make_pool(cfg)
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
        f"interval={interval}s thr={threshold}% "
        f"(usage_threshold) keys={len(pool.all())} "
        f"file={inst.instances_json_path()}"
    )
    print(
        f"自动监测启动 | 间隔 {interval}s | 换号阈值 total>={threshold}% "
        f"| Ctrl+C / sc auto stop 停止"
    )
    last_poll = 0.0
    poll_n = 0
    was_leader = False
    try:
        while True:
            try:
                if parent_pid and not _pid_alive(parent_pid):
                    print("parent 已退出，实例下线")
                    break
                # 每轮热读配置阈值/间隔（对齐 client 可改配置后继续跑）
                cfg = load_config()
                interval = max(1, int(cfg.get("poll_interval") or interval))
                threshold = _usage_threshold(cfg)
                # Key 列表变化时重建池，保留日用量状态较难；简单重建
                new_keys = [str(k) for k in (cfg.get("api_keys") or []) if k]
                if new_keys != pool.to_key_list():
                    pool = _make_pool(cfg)
                else:
                    pool.threshold = int(cfg.get("switch_threshold") or pool.threshold)
                    pool.refresh_interval = int(
                        cfg.get("status_refresh_interval") or pool.refresh_interval
                    )

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
                        poll_interval=interval,
                        usage_threshold=threshold,
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
                            try:
                                _leader_tick(
                                    iid, poll_n, interval, threshold, pool, cfg
                                )
                            except Exception as tick_exc:
                                print(
                                    f"#{poll_n} leader tick 异常: "
                                    f"{type(tick_exc).__name__}: {tick_exc}"
                                )
                            if not _still_leader(iid):
                                print("leader 变更，auto tick 后立即停止")
                                was_leader = False
                                write_status(auto_running=False, auto_pid=None)
                                set_action(
                                    "ok", f"follower 监听 x{inst.online_count()}"
                                )
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
            except Exception as loop_exc:
                # 单轮失败不得退出守护：否则 statusLine 长期 STALE
                print(
                    f"auto loop 异常（继续）: "
                    f"{type(loop_exc).__name__}: {loop_exc}"
                )
                time.sleep(1.0)
            time.sleep(inst.HEARTBEAT_SEC)
    except KeyboardInterrupt:
        print("auto 已停止")
    finally:
        try:
            inst.unregister(iid)
        except Exception:
            pass
        try:
            if _read_auto_pid() == os.getpid():
                _pid_path().unlink(missing_ok=True)
        except Exception:
            pass
        try:
            doc = inst.read_instances()
            write_status(
                auto_running=bool(doc.get("leader_id")),
                auto_pid=None,
                instance_count=inst.online_count(doc),
                leader_id=doc.get("leader_id"),
            )
            if not doc.get("leader_id"):
                set_action("idle", "auto 已停止")
        except Exception:
            pass
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
            "  doctor             自检 hot-auth 补丁与 Bearer sub 对照\n"
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
    if cmd == "doctor":
        return cmd_doctor()
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
