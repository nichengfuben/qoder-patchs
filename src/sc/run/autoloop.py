from __future__ import annotations

"""Auto loop tick, leader prune, and foreground runner."""

import os
import time
from typing import Any, Dict, Optional

from sc.core import api, auth
from sc.core.config import load_config
from sc.core.keys import KeyPool
from sc.run import instances as inst
from sc.run.auto import (
    kill_legacy_exclusive_auto,
    pid_alive,
    pid_path,
    read_auto_pid,
    still_leader,
    write_pid,
)
from sc.run.pull import (
    agent_switch_requested,
    clear_agent_switch_request,
    do_pull_and_write,
    make_pool,
    pull_until_acceptable_usage,
    snapshot_account,
    snapshot_usage,
    usage_threshold,
)
from sc.run.status_store import read_status, set_action, write_status


def leader_prune_stale(instance_id: str) -> Dict[str, Any]:
    with inst._file_lock():  # noqa: SLF001
        data = inst._read_unlocked()  # noqa: SLF001
        inst._elect(data)  # noqa: SLF001
        if data.get("leader_id") != instance_id:
            inst._write_unlocked(data)  # noqa: SLF001
            return data
        removed = inst._prune_by_timestamp(data)  # noqa: SLF001
        inst._elect(data)  # noqa: SLF001
        if removed:
            data["last_prune_at"] = time.time()
            data["last_prune_removed"] = removed
        inst._write_unlocked(data)  # noqa: SLF001
        return data


def follower_clear_stale_leader(instance_id: str) -> Dict[str, Any]:
    with inst._file_lock():  # noqa: SLF001
        data = inst._read_unlocked()  # noqa: SLF001
        now = time.time()
        lid = data.get("leader_id")
        if lid and lid == instance_id:
            inst._elect(data, now=now)  # noqa: SLF001
            inst._write_unlocked(data)  # noqa: SLF001
            return data
        if lid:
            info = (data.get("instances") or {}).get(lid)
            gone = (not isinstance(info, dict)) or (
                not inst._instance_active(info, now=now)  # noqa: SLF001
            )
            if gone:
                (data.get("instances") or {}).pop(lid, None)
                data["leader_id"] = None
                usage = data.get("usage")
                if isinstance(usage, dict) and (
                    usage.get("leader_id") == lid
                    or inst._is_stale(float(usage.get("published_at") or 0), now=now)  # noqa: SLF001
                ):
                    data["usage"] = {}
                data["last_follower_clear_at"] = now
                data["last_follower_cleared"] = lid
        inst._elect(data, now=now)  # noqa: SLF001
        inst._write_unlocked(data)  # noqa: SLF001
        return data


def apply_shared_usage(doc: dict) -> bool:
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
        if not isinstance(info, dict) or not inst._instance_active(info):  # noqa: SLF001
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


def _leader_fetch_usage(token: str, cfg: dict, n: int) -> dict:
    return api.parse_usage(
        api.fetch_usage(token, timeout=float(cfg.get("request_timeout") or 20))
    )


def _limit_hit_detail(usage: dict, threshold: float) -> str:
    parts: list[str] = []
    total = float(usage.get("total_pct") or 0)
    auto = float(usage.get("auto_pct") or 0)
    api = float(usage.get("api_pct") or 0)
    if total >= threshold:
        parts.append(f"total={total:.1f}%")
    if auto >= threshold:
        parts.append(f"auto={auto:.1f}%")
    if api >= threshold:
        parts.append(f"api={api:.1f}%")
    if str(usage.get("membership") or "").lower() == "free" and auto >= 50.0:
        parts.append(f"free auto={auto:.1f}%")
    return ", ".join(parts) if parts else f"total={total:.1f}%"


def _leader_handle_over_threshold(
    instance_id: str, n: int, pool: KeyPool, cfg: dict, threshold: float, usage: dict
) -> None:
    if not still_leader(instance_id):
        print(f"#{n} 换号前失去 leader，立即停")
        return
    detail = _limit_hit_detail(usage, threshold)
    set_action("switching", f"#{n} 超阈值 {detail} >= {threshold}%")
    print(f"达到阈值 ({detail} >= {threshold}%)，自动换号...")
    if not pull_until_acceptable_usage(
        pool, cfg, threshold, title_prefix=f"监测#{n}换号", instance_id=instance_id
    ):
        print(f"#{n} 自动换号未获得可用额度，下轮重试")
        set_action("error", f"#{n} 换号未获可用额度", last_error="switch failed")


def _leader_ensure_token(
    instance_id: str, n: int, interval: int, pool: KeyPool, cfg: dict
) -> Optional[str]:
    token = auth.access_token()
    if token:
        return token
    if not still_leader(instance_id):
        return None
    set_action("switching", f"#{n} 无 Token，自动拉号…")
    print(f"#{n} 无 Token，自动拉号...")
    if not still_leader(instance_id) or not do_pull_and_write(pool, cfg):
        print(f"#{n} 拉号失败，{interval}s 后重试")
        set_action("error", f"#{n} 拉号失败", last_error="pull failed")
        return None
    return auth.access_token()


def _leader_try_agent_switch(
    instance_id: str, n: int, pool: KeyPool, cfg: dict, threshold: float
) -> None:
    if not agent_switch_requested():
        return
    set_action("switching", f"#{n} Agent 额度报错，立即换号…")
    print(f"#{n} Agent 额度信号 → 立即换号…")
    if pull_until_acceptable_usage(
        pool, cfg, threshold, title_prefix=f"Agent信号#{n}换号", instance_id=instance_id
    ):
        clear_agent_switch_request()
    else:
        print(f"#{n} Agent 信号换号未获可用额度，下轮重试")


def leader_tick(
    instance_id: str,
    n: int,
    interval: int,
    threshold: float,
    pool: KeyPool,
    cfg: dict,
) -> None:
    inst.heartbeat(instance_id)
    if not still_leader(instance_id):
        print(f"#{n} 已非 leader，跳过 auto tick")
        return
    _leader_try_agent_switch(instance_id, n, pool, cfg, threshold)
    token = _leader_ensure_token(instance_id, n, interval, pool, cfg)
    if not token:
        return
    try:
        if not still_leader(instance_id):
            print(f"#{n} 查询前失去 leader，立即停")
            return
        print(f"#{n} 查询用量...")
        usage = _leader_fetch_usage(token, cfg, n)
        if not still_leader(instance_id):
            print(f"#{n} 查询后失去 leader，丢弃结果并立即停")
            return
        snapshot_account(token)
        snapshot_usage(usage)
        write_status(poll_n=n, last_error="")
        print(
            f"#{n} total={usage['total_pct']:.1f}% "
            f"auto={usage['auto_pct']:.1f}% api={usage['api_pct']:.1f}% "
            f"status={usage.get('status')}"
        )
        if api.is_limit_reached(usage, threshold):
            _leader_handle_over_threshold(instance_id, n, pool, cfg, threshold, usage)
        else:
            set_action("polling", f"#{n} total={usage['total_pct']:.1f}% < {threshold}% 下轮 {interval}s")
            print(f"额度正常 ({usage['total_pct']:.1f}% < {threshold}%)")
    except Exception as exc:
        hint = api.short_error(exc)
        print(f"#{n} 查询用量失败: {hint}")
        transient = api.is_transient_net_error(exc) or hint in (
            "SSL断连", "SSL失败", "超时", "网络错误", "连接重置", "DNS失败",
        )
        if not transient:
            set_action("polling", f"#{n} 用量查询失败: {hint}", last_error=hint)


def _reload_pool_cfg(pool: KeyPool, cfg: dict) -> KeyPool:
    new_keys = [str(k) for k in (cfg.get("api_keys") or []) if k]
    if new_keys != pool.to_key_list():
        return make_pool(cfg)
    pool.threshold = int(cfg.get("switch_threshold") or pool.threshold)
    pool.refresh_interval = int(cfg.get("status_refresh_interval") or pool.refresh_interval)
    return pool


def _resolve_leader_doc(iid: str, doc: dict, parent_pid: Optional[int]) -> tuple[dict, bool]:
    leader_now = inst.is_leader(iid, doc)
    if leader_now:
        doc = leader_prune_stale(iid)
        return doc, inst.is_leader(iid, doc)
    prev_leader = doc.get("leader_id")
    doc = follower_clear_stale_leader(iid)
    if prev_leader and doc.get("leader_id") != prev_leader:
        print(f"follower 清过期 leader={prev_leader} → new={doc.get('leader_id') or '-'}")
    return doc, inst.is_leader(iid, doc)


def _run_leader_poll(
    iid: str, poll_n: int, interval: int, threshold: float, pool: KeyPool, cfg: dict, doc: dict
) -> tuple[int, bool]:
    n_online = inst.online_count(doc)
    write_status(
        instance_count=n_online, leader_id=doc.get("leader_id"), auto_running=True,
        auto_pid=os.getpid(), instance_id=iid, poll_interval=interval, usage_threshold=threshold,
    )
    if not still_leader(iid):
        print("leader 变更，立即停止 auto")
        write_status(auto_running=False, auto_pid=None)
        set_action("ok", f"follower 监听 x{n_online}")
        return poll_n, False
    poll_n += 1
    try:
        leader_tick(iid, poll_n, interval, threshold, pool, cfg)
    except Exception as tick_exc:
        print(f"#{poll_n} leader tick 异常: {type(tick_exc).__name__}: {tick_exc}")
    if not still_leader(iid):
        print("leader 变更，auto tick 后立即停止")
        write_status(auto_running=False, auto_pid=None)
        set_action("ok", f"follower 监听 x{inst.online_count()}")
        return poll_n, False
    return poll_n, True


def _run_follower(doc: dict, iid: str) -> None:
    n_online = inst.online_count(doc)
    write_status(
        instance_count=n_online, leader_id=doc.get("leader_id"),
        auto_running=False, auto_pid=None, instance_id=iid,
    )
    apply_shared_usage(doc)
    set_action("ok", f"follower 监听 x{n_online}")


def _auto_loop_body(
    iid: str, parent_pid: Optional[int], pool: KeyPool,
    interval: int, threshold: float, poll_n: int, last_poll: float, was_leader: bool,
) -> tuple[KeyPool, int, int, float, bool, bool]:
    cfg = load_config()
    interval = max(1, int(cfg.get("poll_interval") or interval))
    threshold = usage_threshold(cfg)
    pool = _reload_pool_cfg(pool, cfg)
    doc = inst.heartbeat(iid, parent_pid=parent_pid)
    if iid not in (doc.get("instances") or {}):
        print("实例已被清理（parent 退出或冲突），结束")
        return pool, poll_n, interval, last_poll, was_leader, True
    doc, leader_now = _resolve_leader_doc(iid, doc, parent_pid)
    if leader_now:
        if not was_leader:
            set_action("polling", f"成为 leader，开始 auto x{inst.online_count(doc)}")
            print(f"leader acquired → 开始 auto online={inst.online_count(doc)}")
            was_leader = True
            last_poll = 0.0
        now = time.time()
        if now - last_poll >= interval:
            poll_n, was_leader = _run_leader_poll(
                iid, poll_n, interval, threshold, pool, cfg, doc
            )
            if was_leader:
                last_poll = now
    elif was_leader:
        print("leader 变更，立即停止 auto → follower")
        was_leader = False
        last_poll = 0.0
        write_status(
            instance_count=inst.online_count(doc), leader_id=doc.get("leader_id"),
            auto_running=False, auto_pid=None, instance_id=iid,
        )
        set_action("ok", f"follower 监听 x{inst.online_count(doc)}")
    else:
        _run_follower(doc, iid)
    return pool, poll_n, interval, last_poll, was_leader, False


def _auto_cleanup(iid: str) -> None:
    try:
        inst.unregister(iid)
    except Exception:
        pass
    try:
        if read_auto_pid() == os.getpid():
            pid_path().unlink(missing_ok=True)
    except Exception:
        pass
    try:
        doc = inst.read_instances()
        write_status(
            auto_running=bool(doc.get("leader_id")), auto_pid=None,
            instance_count=inst.online_count(doc), leader_id=doc.get("leader_id"),
        )
        if not doc.get("leader_id"):
            set_action("idle", "auto 已停止")
    except Exception:
        pass


def run_auto_foreground(*, parent_pid: Optional[int] = None) -> int:
    kill_legacy_exclusive_auto()
    cfg = load_config()
    interval = max(1, int(cfg.get("poll_interval") or 5))
    threshold = usage_threshold(cfg)
    pool = make_pool(cfg)
    iid = inst.register_instance(parent_pid=parent_pid)
    write_pid()
    snapshot_account()
    write_status(poll_interval=interval, usage_threshold=threshold, poll_n=0, instance_id=iid)
    print(
        f"instance={iid} parent={parent_pid or '-'} interval={interval}s thr={threshold}% "
        f"(usage_threshold) keys={len(pool.all())} file={inst.instances_json_path()}"
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
                if parent_pid and not pid_alive(parent_pid):
                    print("parent 已退出，实例下线")
                    break
                pool, poll_n, interval, last_poll, was_leader, stop = _auto_loop_body(
                    iid, parent_pid, pool, interval, threshold, poll_n, last_poll, was_leader
                )
                if stop:
                    break
            except Exception as loop_exc:
                print(f"auto loop 异常（继续）: {type(loop_exc).__name__}: {loop_exc}")
                time.sleep(1.0)
            time.sleep(inst.HEARTBEAT_SEC)
    except KeyboardInterrupt:
        print("auto 已停止")
    finally:
        _auto_cleanup(iid)
    return 0
