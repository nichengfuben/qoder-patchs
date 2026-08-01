from __future__ import annotations

"""Cursor Agent patch entry point: CursorAgentPatch class."""

import time
from pathlib import Path
from typing import Optional

from loguru import logger


def _is_windows() -> bool:
    import os

    return os.name == "nt"

from core.patch_base import PatchBase, PatchMetadata, PatchResult, PatchStatus
from patches.cursor.cursor_hotauth import (
    DISK_MARKER,
    EPHEMERAL_NULL_MARKER,
    FOOTER_KEEP_MARKER,
    MARKER,
    SLASH_MARKER,
    STATUS_INTERVAL_MARKER,
    apply_hot_auth_replacements,
    clear_node_compile_cache,
)
from patches.cursor.cursor_hotauth import BOOT_MARKER
from patches.cursor.cursor_hotauth import _COMPILE_CACHE_NEW, _COMPILE_CACHE_OLD
from patches.cursor.cursor_chunks import (
    _DISK_BEARER_OVERRIDE,
    _FOOTER_KEEP_OLD,
    _STATUS_INTERVAL_OLD,
)
from patches.cursor.cursor_repls import _GET_ACCESS_NOCACHE, _REPLACEMENTS
from patches.cursor.cursor_launchers import (
    _UNIX_WRAPPER_MARKER,
    ensure_sc_config_from_client,
    find_client_config,
    install_unix_launchers,
    install_win_launchers,
    rollback_boot_lines,
    write_script,
)
from patches.cursor import cursor_patchops as ops
from sc.cli_config import merge_status_line
from sc.core.paths import find_cursor_agent_bundle, find_cursor_agent_root
from utils.paths import get_project_root

# Re-export markers for tests / doctor
__all__ = [
    "CursorAgentPatch",
    "BOOT_MARKER",
    "DISK_MARKER",
    "EPHEMERAL_NULL_MARKER",
    "FOOTER_KEEP_MARKER",
    "MARKER",
    "SLASH_MARKER",
    "STATUS_INTERVAL_MARKER",
    "_COMPILE_CACHE_NEW",
    "_COMPILE_CACHE_OLD",
    "_DISK_BEARER_OVERRIDE",
    "_GET_ACCESS_NOCACHE",
    "_REPLACEMENTS",
    "apply_hot_auth_replacements",
    "find_client_config",
]


class CursorAgentPatch(PatchBase):
    """Hot-reload auth + auto-boot sc auto + /sc slash + statusline。"""

    @property
    def metadata(self) -> PatchMetadata:
        return PatchMetadata(
            name="cursor-agent",
            display_name="Cursor Agent 热更新与自动换号",
            description=(
                "AuthStorage/keychain/ephemeral 全部强制读盘；禁用 NODE_COMPILE_CACHE；"
                "启动 agent 时自动后台 sc auto；注入 /sc pull|usage；statusline 定时刷新。"
            ),
            version="2.4.0",
            author="nichengfuben",
            target_files=("index.js", "*.index.js"),
            tags=("cursor-agent", "auth", "hot-reload", "sc", "auto", "statusline", "slash"),
            reversible=True,
        )

    def validate(self, bundle_dir: Path) -> list[str]:
        issues: list[str] = []
        target = ops.resolve_bundle(bundle_dir)
        if target is None:
            issues.append("未找到 cursor-agent versions/*/index.js（Win/Unix 安装根）")
            return issues
        index = ops.index_js(target)
        if not index.exists():
            issues.append(f"Target file does not exist: {index}")
        elif not index.is_file():
            issues.append(f"Target is not a file: {index}")
        if find_cursor_agent_root() is None:
            issues.append("未找到 cursor-agent 安装根")
        return issues

    def check(self, bundle_dir: Path) -> PatchStatus:
        target = ops.resolve_bundle(bundle_dir)
        if target is None:
            return PatchStatus.UNKNOWN
        index = ops.index_js(target)
        if not index.exists():
            return PatchStatus.UNKNOWN
        text = index.read_text(encoding="utf-8", errors="ignore")
        root = find_cursor_agent_root()
        flags = _check_flags(target, root, text)
        if all(flags.values()):
            return PatchStatus.APPLIED
        if any(flags.values()):
            return PatchStatus.PARTIAL
        return PatchStatus.NOT_APPLIED

    def apply(self, bundle_dir: Path, dry_run: bool = False) -> PatchResult:
        return _apply_patch(self, bundle_dir, dry_run)

    def rollback(self, bundle_dir: Path, dry_run: bool = False) -> PatchResult:
        return _rollback_patch(self, bundle_dir, dry_run)


def _apply_patch(patch: CursorAgentPatch, bundle_dir: Path, dry_run: bool) -> PatchResult:
    start = time.monotonic()
    target = ops.resolve_bundle(bundle_dir)
    if target is None:
        return PatchResult(
            status=PatchStatus.FAILED,
            message="未找到 cursor-agent version 目录（index.js）",
            patch_name=patch.metadata.name,
            duration_ms=int((time.monotonic() - start) * 1000),
            error="bundle not found",
        )
    index = ops.index_js(target)
    content = index.read_text(encoding="utf-8", errors="ignore")
    hot_hits, _, _ = ops.patch_hot_auth(index, dry_run=True)
    root = find_cursor_agent_root()
    iv_hits, _, _ = ops.patch_statusline_interval(target, dry_run=True)
    ft_hits, _, _ = ops.patch_footer_keep(target, dry_run=True)
    ps1_hits, _, _ = ops.patch_compile_cache_ps1(root, dry_run=True) if root else (0, [], [])
    if dry_run:
        return PatchResult(
            status=PatchStatus.APPLIED if hot_hits >= 1 or MARKER in content else PatchStatus.FAILED,
            message=(
                f"[dry-run] hot-auth hits={hot_hits}, status-interval={iv_hits}, "
                f"footer-keep={ft_hits}, compile-cache-ps1={ps1_hits}, would install sc/auto-boot at {root}"
            ),
            patch_name=patch.metadata.name,
            duration_ms=int((time.monotonic() - start) * 1000),
        )
    if hot_hits == 0 and MARKER not in content:
        return PatchResult(
            status=PatchStatus.FAILED,
            message="未匹配到 AuthStorage 缓存片段（cursor-agent 版本可能已变）",
            patch_name=patch.metadata.name,
            duration_ms=int((time.monotonic() - start) * 1000),
            error="pattern miss",
        )
    files, backups, stats = _apply_all_phases(index, target, root)
    return PatchResult(
        status=PatchStatus.APPLIED,
        message=(
            f"hot-auth(v2 ephemeral-off) + auto-boot + /sc + statusline 已应用 "
            f"(hot={stats['hot']}, slash={stats['slash']}, interval={stats['iv']}, "
            f"footer={stats['ft']}, boot={stats['boot']}, launchers={stats['ag']}, "
            f"config={stats['cfg']}, root={root})"
        ),
        patch_name=patch.metadata.name,
        files_modified=files,
        backups_created=backups,
        duration_ms=int((time.monotonic() - start) * 1000),
    )


def _uichunk_texts(target: Path) -> list[str]:
    texts: list[str] = []
    for p in target.glob("*.index.js"):
        if not p.is_file():
            continue
        try:
            texts.append(p.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
    return texts


def _optional_uichunk_ok(texts: list[str], marker: str, old: str) -> bool:
    """已打上标记，或本版本根本没有对应片段（不适用）→ 视为通过。"""
    if any(marker in t for t in texts):
        return True
    return not any(old in t for t in texts)


def _check_flags(target: Path, root: Optional[Path], text: str) -> dict:
    hot_ok = MARKER in text and EPHEMERAL_NULL_MARKER in text and DISK_MARKER in text
    chunks = _uichunk_texts(target)
    return {
        "hot": hot_ok,
        "sc": _sc_launchers_ok(root),
        "boot": _boot_ok(root, target),
        "slash": len(ops.slash_chunks(target)) > 0,
        # interval/footer 依赖特定 UI chunk；新版本对不上时不算失败
        "interval": _optional_uichunk_ok(chunks, STATUS_INTERVAL_MARKER, _STATUS_INTERVAL_OLD),
        "footer": _optional_uichunk_ok(chunks, FOOTER_KEEP_MARKER, _FOOTER_KEEP_OLD),
    }


def _sc_launchers_ok(root: Optional[Path]) -> bool:
    if root is None:
        return False
    if _is_windows():
        return (root / "sc.cmd").exists() and (root / "sc-statusline.cmd").exists()
    return (root / "sc").exists() and (root / "sc-statusline").exists()


def _boot_ok(root: Optional[Path], target: Path) -> bool:
    if root is None:
        return False
    if _is_windows():
        boot_cmd = root / "cursor-agent.cmd"
        if not boot_cmd.exists():
            return False
        return BOOT_MARKER in boot_cmd.read_text(encoding="utf-8", errors="ignore")
    agent = target / "cursor-agent"
    real = target / "cursor-agent.bin"
    if not agent.is_file() or not real.is_file():
        return False
    return _UNIX_WRAPPER_MARKER in agent.read_text(encoding="utf-8", errors="ignore")


def _apply_all_phases(index: Path, target: Path, root: Optional[Path]) -> tuple:
    files: list[Path] = []
    backups: list[Path] = []
    stats = {"hot": 0, "slash": 0, "iv": 0, "ft": 0, "boot": False, "ag": False, "cfg": None}
    hot_hits, hot_file, hot_bak = ops.patch_hot_auth(index, dry_run=False)
    stats["hot"] = hot_hits
    if hot_file:
        files.append(hot_file)
    if hot_bak:
        backups.append(hot_bak)
    _apply_side_patches(target, root, files, backups, stats)
    return files, backups, stats


def _apply_side_patches(
    target: Path, root: Optional[Path], files: list, backups: list, stats: dict
) -> None:
    if root is not None:
        _, ps1_files, ps1_baks = ops.patch_compile_cache_ps1(root, dry_run=False)
        files.extend(ps1_files)
        backups.extend(ps1_baks)
    cleared = clear_node_compile_cache()
    if cleared:
        logger.info("Cleared NODE_COMPILE_CACHE dir {}", cleared)
    slash_hits, slash_files, slash_baks = ops._inject_slash(target, dry_run=False)
    stats["slash"] = slash_hits
    files.extend(slash_files)
    backups.extend(slash_baks)
    iv_hits, iv_files, iv_baks = ops.patch_statusline_interval(target, dry_run=False)
    stats["iv"] = iv_hits
    files.extend(iv_files)
    backups.extend(iv_baks)
    ft_hits, ft_files, ft_baks = ops.patch_footer_keep(target, dry_run=False)
    stats["ft"] = ft_hits
    files.extend(ft_files)
    backups.extend(ft_baks)
    cfg_copied = ensure_sc_config_from_client(force=False)
    stats["cfg"] = cfg_copied
    if cfg_copied:
        files.append(cfg_copied)
    if root is not None:
        _apply_root_launchers(root, target, files, backups, stats)


def _apply_root_launchers(
    root: Path, target: Path, files: list, backups: list, stats: dict
) -> None:
    files.extend(_install_sc_launchers(root))
    if _is_windows():
        boot_ok, boot_file, boot_bak = ops.patch_boot_cmd(root, dry_run=False)
        stats["boot"] = boot_ok
        if boot_file:
            files.append(boot_file)
        if boot_bak:
            backups.append(boot_bak)
        ag_ok, ag_files, ag_baks = ops.patch_launchers(root, dry_run=False)
        stats["ag"] = ag_ok
        files.extend(ag_files)
        backups.extend(ag_baks)
        sl = root / "sc-statusline.cmd"
    else:
        boot_ok, uw_files, uw_baks = ops.patch_unix_wrapper(target, dry_run=False)
        stats["boot"] = boot_ok
        files.extend(uw_files)
        backups.extend(uw_baks)
        sl = root / "sc-statusline"
    cfg_path = merge_status_line(str(sl.resolve()))
    files.append(cfg_path)
    logger.info("Wired statusLine → {}", cfg_path)


def _install_sc_launchers(root: Path) -> list[Path]:
    src = get_project_root() / "src"
    if _is_windows():
        return install_win_launchers(root, src)
    return install_unix_launchers(root, src)


def _rollback_patch(patch: CursorAgentPatch, bundle_dir: Path, dry_run: bool) -> PatchResult:
    start = time.monotonic()
    target = ops.resolve_bundle(bundle_dir)
    if target is None:
        return PatchResult(
            status=PatchStatus.FAILED,
            message="未找到 cursor-agent bundle",
            patch_name=patch.metadata.name,
            duration_ms=int((time.monotonic() - start) * 1000),
            error="missing",
        )
    if dry_run:
        return PatchResult(
            status=PatchStatus.NOT_APPLIED,
            message="[dry-run] would rollback hot-auth, footer-keep, boot, slash, sc launchers",
            patch_name=patch.metadata.name,
            duration_ms=int((time.monotonic() - start) * 1000),
        )
    files = _rollback_index(target)
    files.extend(_rollback_chunks(target))
    files.extend(_rollback_root_launchers())
    return PatchResult(
        status=PatchStatus.NOT_APPLIED,
        message="已回滚 hot-auth、status-interval、footer-keep、auto-boot、slash，并移除 sc 启动器",
        patch_name=patch.metadata.name,
        files_modified=files,
        duration_ms=int((time.monotonic() - start) * 1000),
    )


def _rollback_index(target: Path) -> list[Path]:
    from patches.cursor.cursor_repls import _REPLACEMENTS

    index = ops.index_js(target)
    content = index.read_text(encoding="utf-8", errors="ignore")
    restored = content
    for old, new in _REPLACEMENTS:
        if new in restored:
            restored = restored.replace(new, old, 1)
    files: list[Path] = []
    if restored != content:
        index.write_text(restored, encoding="utf-8")
        files.append(index)
    return files


def _rollback_chunks(target: Path) -> list[Path]:
    files: list[Path] = []
    _, slash_files, _ = ops._strip_slash(target, dry_run=False)
    files.extend(slash_files)
    _, iv_files = ops.strip_statusline_interval(target, dry_run=False)
    files.extend(iv_files)
    _, ft_files = ops.strip_footer_keep(target, dry_run=False)
    files.extend(ft_files)
    files.extend(ops.rollback_unix_wrapper(target))
    return files


def _rollback_root_launchers() -> list[Path]:
    files: list[Path] = []
    root = find_cursor_agent_root()
    if root is None:
        return files
    if _is_windows():
        cmd = root / "cursor-agent.cmd"
        if cmd.exists() and BOOT_MARKER in cmd.read_text(encoding="utf-8", errors="ignore"):
            text = cmd.read_text(encoding="utf-8", errors="ignore")
            write_script(cmd, rollback_boot_lines(text), crlf=True)
            files.append(cmd)
        names = ("sc.cmd", "sc.ps1", "sc-statusline.cmd", "sc-autoboot.ps1")
    else:
        names = ("sc", "sc-statusline", "sc-autoboot.sh")
    for name in names:
        p = root / name
        if p.exists():
            p.unlink()
            files.append(p)
    return files
