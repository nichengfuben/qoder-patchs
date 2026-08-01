from __future__ import annotations

"""Token pull helpers: Key pool, acquire, write auth."""

import os
import time
from typing import Optional

from sc.core import api, auth
from sc.core.config import load_config
from sc.core.keys import KeyPool, KeyState
from sc.core.paths import auth_json_path, config_json_path
from sc.run import instances as inst
from sc.run.status_store import set_action, status_json_path, write_status


def mask_key(key: str) -> str:
    return f"{key[:6]}...{key[-4:]}" if len(key) > 10 else key


def usage_threshold(cfg: dict) -> float:
    if cfg.get("usage_threshold") is not None:
        return float(cfg.get("usage_threshold"))
    return 90.0


def _request_agent_continue(text: str = "继续") -> None:
    try:
        from sc.run.status_store import request_continue_nudge

        nudge_path = request_continue_nudge(text)
        print(f"已请求 Agent 自动继续 → {nudge_path}")
    except Exception as nudge_exc:
        print(f"写入自动继续信号失败: {nudge_exc}")


def make_pool(cfg: dict) -> KeyPool:
    keys = [str(k) for k in (cfg.get("api_keys") or []) if k]
    return KeyPool(
        keys=keys,
        threshold=int(cfg.get("switch_threshold") or 80),
        refresh_interval=int(cfg.get("status_refresh_interval") or 60),
    )


def snapshot_account(access: Optional[str] = None, email: str = "", card: str = "") -> None:
    token = access or auth.access_token()
    uid = api.extract_user_id(token) if token else ""
    cfg = load_config()
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


def snapshot_usage(usage: dict) -> None:
    from sc.run.status_store import read_status

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


def refresh_key_state(pool: KeyPool, s: KeyState, cfg: dict) -> bool:
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


def ensure_usable_key(pool: KeyPool, cfg: dict) -> Optional[KeyState]:
    total = len(pool.all())
    if total == 0:
        return None
    for _ in range(total):
        s = pool.current
        if s is None:
            return None
        if pool.is_stale(s):
            refresh_key_state(pool, s, cfg)
        if pool.should_switch(s):
            print(
                f"Key[{s.masked()}] daily_used={s.daily_used} "
                f">= 阈值 {pool.threshold}，切换..."
            )
            pool.switch_next()
            continue
        return s
    return None


def _handle_api_error(pool: KeyPool, s: KeyState, e: api.ApiError) -> None:
    if e.status == 403:
        payload = e.payload
        if payload.get("error") == "Daily limit reached":
            s.daily_used = payload.get("daily_used", s.daily_used)
            s.daily_limit = payload.get("daily_limit", s.daily_limit)
            s.last_checked = time.time()
            print(f"Key[{s.masked()}] 每日上限 ({s.daily_used}/{s.daily_limit})，切换")
        else:
            s.is_active = False
            print(f"Key[{s.masked()}] 已被禁用")
        pool.switch_next()
        return
    if e.status == 429:
        wait = float(e.payload.get("retry_after") or 5)
        print(f"速率限制，等待 {wait}s")
        time.sleep(wait)
        return
    if e.status == 503:
        print("账号池无可用卡密，3s 后重试")
        time.sleep(3)
        return
    if e.status == 500:
        print("卡密尝试全部失败，切换 Key")
        pool.switch_next()
        return
    if e.status == 401:
        s.is_active = False
        print(f"Key[{s.masked()}] 无效，剔除并切换")
        pool.switch_next()
        return
    print(f"未知错误 HTTP {e.status}")
    time.sleep(2)


def _handle_pull_exc(exc: Exception) -> None:
    hint = api.short_error(exc)
    transient = api.is_transient_net_error(exc) or hint in (
        "SSL断连", "SSL失败", "超时", "网络错误", "连接重置", "DNS失败",
    )
    if transient:
        print(f"pull 暂不可用: {hint}，2s 后重试")
    else:
        print(f"pull 失败: {hint}")
    time.sleep(2)


def acquire_token(pool: KeyPool, cfg: dict) -> Optional[dict]:
    max_retry = int(cfg.get("max_retry_per_pull") or 3)
    timeout = float(cfg.get("request_timeout") or 20)
    base = str(cfg.get("base_url") or "")
    for attempt in range(1, max_retry + 1):
        s = ensure_usable_key(pool, cfg)
        if s is None:
            print("所有 Key 均已达阈值或不可用")
            return None
        set_action("pulling", f"pull [{attempt}/{max_retry}] via {s.masked()}", last_error="")
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
            _handle_api_error(pool, s, e)
        except Exception as exc:
            _handle_pull_exc(exc)
    print(f"已重试 {max_retry} 次，未能获取 Token")
    return None


def do_pull_and_write(pool: KeyPool, cfg: dict) -> bool:
    if pool.is_empty():
        set_action("error", "无 API Key", last_error="missing api key")
        print("无 API Key。请先: sc addkey <sc_xxx> 或编辑", config_json_path())
        return False
    result = acquire_token(pool, cfg)
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
    snapshot_account(access, email=email, card=card)
    write_status(last_pull_at=time.strftime("%Y-%m-%d %H:%M:%S"), last_error="")
    print(f"已写入 {auth_json_path()} email={email or '-'} card={card or '-'}")
    print(f"uid={api.extract_user_id(access) or '-'}")
    print("(已打 cursor-agent 热更新补丁时无需重启)")
    return True


def _check_usage_ok(
    pool: KeyPool,
    cfg: dict,
    threshold: float,
    attempt: int,
    attempts: int,
    title_prefix: str,
) -> bool:
    at = auth.access_token()
    if not at:
        print("换号后无法读取本地 Token")
        return False
    timeout = float(cfg.get("request_timeout") or 20)
    try:
        print(f"校验用量 [{attempt}/{attempts}]...")
        usage = api.parse_usage(api.fetch_usage(at, timeout=timeout))
        snapshot_account(at)
        snapshot_usage(usage)
        print(
            f"{title_prefix} #{attempt}/{attempts} "
            f"total={usage['total_pct']:.1f}% "
            f"auto={usage['auto_pct']:.1f}% api={usage['api_pct']:.1f}%"
        )
        if not api.is_limit_reached(usage, threshold):
            set_action("ok", f"换号成功 total={usage['total_pct']:.1f}% < {threshold}%")
            print(f"换号成功，额度正常 ({usage['total_pct']:.1f}% < {threshold}%)")
            _request_agent_continue()
            return True
        if attempt < attempts:
            set_action("switching", f"新号仍超阈值 (>={threshold}%)，继续拉号")
            print(
                f"新号仍超阈值 ({usage['total_pct']:.1f}% >= {threshold}%)，"
                f"立即再次换号..."
            )
            return False
        set_action("error", f"连续换号 {attempts} 次仍超阈值", last_error="still over threshold")
        print(f"已连续换号 {attempts} 次仍超阈值 ({usage['total_pct']:.1f}% >= {threshold}%)")
        return False
    except Exception as exc:
        hint = api.short_error(exc)
        print(f"校验新号用量失败: {hint}")
        set_action("ok", f"pull 已写入，用量校验失败: {hint}")
        # auth 已换新；用量 API 失败时仍让 Agent 用新号重试，避免卡在旧额度 UI
        if attempt >= attempts:
            _request_agent_continue()
            return True
        return False


def pull_until_acceptable_usage(
    pool: KeyPool,
    cfg: dict,
    threshold: float,
    *,
    max_attempts: Optional[int] = None,
    title_prefix: str = "新号用量",
) -> bool:
    attempts = max_attempts if max_attempts is not None else int(cfg.get("max_retry_per_pull") or 3)
    for attempt in range(1, attempts + 1):
        if not do_pull_and_write(pool, cfg):
            print(f"换号失败 ({attempt}/{attempts})" if attempt > 1 else "自动换号失败")
            return False
        if _check_usage_ok(pool, cfg, threshold, attempt, attempts, title_prefix):
            return True
    return False
