from __future__ import annotations

"""User-facing sc commands (except auto loop)."""

import json
import os
from pathlib import Path

from sc.core import api, auth
from sc.core.config import load_config, save_config
from sc.core.paths import auth_json_path, config_json_path, cursor_config_dir
from sc.run import instances as inst
from sc.run.pull import (
    make_pool,
    mask_key,
    pull_until_acceptable_usage,
    snapshot_account,
    snapshot_usage,
    usage_threshold,
)
from sc.run.status_store import set_action, status_json_path, write_status
from sc.run.status_store import format_status_lines, run as statusline_run


def cmd_pull() -> int:
    cfg = load_config()
    pool = make_pool(cfg)
    threshold = usage_threshold(cfg)
    snapshot_account()
    ok = pull_until_acceptable_usage(pool, cfg, threshold, title_prefix="拉号后用量")
    return 0 if ok else 1


def cmd_usage() -> int:
    token = auth.access_token()
    if not token:
        set_action("error", "未找到 Token", last_error="no token")
        print(f"未找到 Token ({auth_json_path()})")
        return 1
    try:
        usage = api.parse_usage(api.fetch_usage(token))
    except Exception as exc:
        print(f"用量查询失败: {api.short_error(exc)}")
        return 1
    snapshot_account(token)
    snapshot_usage(usage)
    write_status(last_error="")
    set_action("ok", f"usage total={usage['total_pct']}%")
    print(
        f"total={usage['total_pct']}%  auto={usage['auto_pct']}%  "
        f"api={usage['api_pct']}%  status={usage['status']}  "
        f"membership={usage.get('membership')}"
    )
    print(f"used={usage.get('used')} remaining={usage.get('remaining')} pool={usage.get('total')}")
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
    snapshot_account(token)
    set_action("ok", f"token uid={uid or '-'}")
    print(f"path={path}\nuid={uid or '-'}\ntoken={mask_key(token)}")
    return 0


def _doctor_check_markers(text: str, patch_cls) -> tuple[bool, dict]:
    from patches.cursor.cursor_agent import DISK_MARKER, EPHEMERAL_NULL_MARKER, MARKER

    checks = {
        "hot-auth marker": MARKER in text,
        "ephemeral null": EPHEMERAL_NULL_MARKER in text,
        "disk bearer": DISK_MARKER in text,
        "no ephemeralToken:R": "ephemeralToken:R," not in text,
        "no cache early-return": "if(this.cachedAccessToken)return this.cachedAccessToken" not in text,
    }
    ok = all(checks.values())
    return ok, checks


def cmd_doctor() -> int:
    from patches.cursor.cursor_agent import CursorAgentPatch
    from sc.core.paths import find_cursor_agent_bundle

    ok = True
    bundle = find_cursor_agent_bundle()
    print(f"bundle: {bundle or '(missing)'}")
    if bundle is None:
        print("FAIL: 未找到 cursor-agent versions/*/index.js")
        return 1
    patch = CursorAgentPatch()
    print(f"patch:  {patch.check(bundle)}")
    text = (bundle / "index.js").read_text(encoding="utf-8", errors="ignore")
    markers_ok, checks = _doctor_check_markers(text, patch)
    for name, good in checks.items():
        print(f"  {'OK' if good else 'FAIL'}: {name}")
    ok = ok and markers_ok
    auth_path = auth_json_path()
    sub = auth.token_subject()
    print(f"auth:   {auth_path}\nauth.sub: {sub or '(none)'}")
    if not sub:
        print("FAIL: auth.json 无可用 accessToken")
        ok = False
    bearer_path = cursor_config_dir() / "agentcli-last-bearer.json"
    print(f"bearer: {bearer_path}")
    ok = _doctor_bearer(bearer_path, sub) and ok
    ok = _doctor_ps1(ok)
    print("doctor: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def _doctor_bearer(bearer_path: Path, sub: str | None) -> bool:
    if not bearer_path.is_file():
        print("WARN: 尚无 agentcli-last-bearer.json（重启 ag 并发一条消息后生成）")
        return True
    try:
        doc = json.loads(bearer_path.read_text(encoding="utf-8"))
        bsub = doc.get("sub")
        print(f"bearer.sub: {bsub}  ts={doc.get('ts')} pid={doc.get('pid')} via={doc.get('via')}")
        if sub and bsub and sub != bsub:
            print("FAIL: auth.sub ≠ bearer.sub — Agent 可能未重启或仍用旧进程")
            return False
        if sub and bsub and sub == bsub:
            print("OK: auth.sub == bearer.sub")
    except Exception as exc:
        print(f"FAIL: 无法解析 last-bearer: {exc}")
        return False
    return True


def _doctor_ps1(ok: bool) -> bool:
    ps1 = Path(os.environ.get("LOCALAPPDATA", "")) / "cursor-agent" / "cursor-agent.ps1"
    if not ps1.is_file():
        return ok
    ps = ps1.read_text(encoding="utf-8", errors="ignore")
    cache_off = "disable NODE_COMPILE_CACHE" in ps
    print(f"  {'OK' if cache_off else 'FAIL'}: NODE_COMPILE_CACHE disabled in cursor-agent.ps1")
    return ok and cache_off


def cmd_addkey(key: str) -> int:
    cfg = load_config()
    keys = list(cfg.get("api_keys") or [])
    if key in keys:
        print("Key 已存在")
        snapshot_account()
        return 0
    keys.append(key)
    cfg["api_keys"] = keys
    save_config(cfg)
    snapshot_account()
    set_action("ok", f"已添加 {mask_key(key)}")
    print(f"已添加 {mask_key(key)} → {config_json_path()}")
    return 0


def cmd_status() -> int:
    cfg = load_config()
    keys = cfg.get("api_keys") or []
    doc = inst.read_instances()
    leader = doc.get("leader_id")
    n_online = inst.online_count(doc)
    snapshot_account()
    write_status(auto_running=bool(leader), keys=len(keys), instance_count=n_online, leader_id=leader)
    token = auth.access_token()
    if token:
        try:
            usage = api.parse_usage(api.fetch_usage(token))
            snapshot_usage(usage)
            set_action("ok" if not leader else "polling", f"status total={usage['total_pct']}%")
        except Exception:
            pass
    else:
        set_action("idle", "无 Token")
    _print_status_report(cfg, keys, doc, leader, n_online, token)
    return 0


def _print_status_report(cfg, keys, doc, leader, n_online, token) -> None:
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
        print(f"  - {mask_key(k)}")
    print(f"poll={cfg.get('poll_interval')}s threshold={usage_threshold(cfg)}%")
    print(f"online: {n_online}  leader={leader or '-'}")
    for iid, info in (doc.get("instances") or {}).items():
        if not isinstance(info, dict):
            continue
        print(
            f"  - {iid[:8]}… role={info.get('role')} pid={info.get('pid')} "
            f"hb={info.get('heartbeat_at')}"
        )
    print("auto:   leader running" if leader else "auto:   no leader (启动 sc auto / agent)")
    for line in format_status_lines():
        print("--- live ---")
        print(line)


def cmd_statusline() -> int:
    return statusline_run()
