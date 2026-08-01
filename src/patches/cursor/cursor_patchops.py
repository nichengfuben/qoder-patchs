from __future__ import annotations

"""Cursor Agent patch operations (index.js chunks, boot, launchers)."""

import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

from loguru import logger

from patches.cursor.cursor_hotauth import (
    FOOTER_KEEP_MARKER,
    MARKER,
    SLASH_MARKER,
    STATUS_INTERVAL_MARKER,
    _COMPILE_CACHE_NEW,
    _COMPILE_CACHE_OLD,
    apply_hot_auth_replacements,
    clear_node_compile_cache,
)
from patches.cursor.cursor_chunks import (
    _FOOTER_KEEP_NEW,
    _FOOTER_KEEP_OLD,
    _SLASH_ANCHOR,
    _SLASH_INJECT,
    _STATUS_INTERVAL_NEW,
    _STATUS_INTERVAL_OLD,
    inject_nudge as _inject_nudge,
    strip_nudge as _strip_nudge,
)
from patches.cursor.cursor_launchers import (
    _AG_CMD,
    _BOOT_BLOCK,
    _CURSOR_AGENT_CMD_TAIL,
    patch_unix_wrapper,  # noqa: F401 — re-export
    rollback_unix_wrapper,  # noqa: F401 — re-export
    write_script,
)
from sc.core.paths import find_cursor_agent_bundle


def index_js(bundle_dir: Path) -> Path:
    return bundle_dir / "index.js"

def slash_chunks(bundle_dir: Path) -> list[Path]:
    hits: list[Path] = []
    for path in bundle_dir.glob("*.index.js"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if SLASH_MARKER in text or 'ue.push({id:"sc"' in text:
            hits.append(path)
    return hits

def resolve_bundle(bundle_dir: Optional[Path] = None) -> Optional[Path]:
    if bundle_dir is not None and (bundle_dir / "index.js").exists():
        return bundle_dir
    return find_cursor_agent_bundle()

def patch_hot_auth(index: Path, dry_run: bool) -> tuple[int, Optional[Path], Optional[Path]]:
    content = index.read_text(encoding="utf-8", errors="ignore")
    modified, hits = apply_hot_auth_replacements(content)
    if dry_run or modified == content:
        return hits, None, None
    assert_js_syntax(index, modified)
    bak = index.with_suffix(index.suffix + f".bak.{time.strftime('%Y%m%d%H%M%S')}")
    bak.write_text(content, encoding="utf-8")
    index.write_text(modified, encoding="utf-8")
    return hits, index, bak

def patch_compile_cache_ps1(
    root: Path, dry_run: bool
) -> tuple[int, list[Path], list[Path]]:
    """根目录与当前 version 的 cursor-agent.ps1：禁用 NODE_COMPILE_CACHE。"""
    files: list[Path] = []
    backups: list[Path] = []
    hits = 0
    candidates = [root / "cursor-agent.ps1"]
    bundle = find_cursor_agent_bundle()
    if bundle is not None:
        candidates.append(bundle / "cursor-agent.ps1")
    seen: set[Path] = set()
    for path in candidates:
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved in seen or not path.is_file():
            continue
        seen.add(resolved)
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "agentcli-hot-auth: disable NODE_COMPILE_CACHE" in text:
            hits += 1
            continue
        if _COMPILE_CACHE_OLD not in text:
            continue
        hits += 1
        if dry_run:
            continue
        bak = path.with_suffix(path.suffix + f".bak.{time.strftime('%Y%m%d%H%M%S')}")
        bak.write_text(text, encoding="utf-8")
        backups.append(bak)
        write_script(
            path,
            text.replace(_COMPILE_CACHE_OLD, _COMPILE_CACHE_NEW, 1),
            crlf=False,
        )
        files.append(path)
        logger.info("Disabled NODE_COMPILE_CACHE in {}", path)
    return hits, files, backups

def patch_statusline_interval(
    bundle_dir: Path, dry_run: bool
) -> tuple[int, list[Path], list[Path]]:
    """把 use-status-line 的 debounce 改成按 updateIntervalMs 的 setInterval。"""
    files: list[Path] = []
    backups: list[Path] = []
    hits = 0
    for chunk in bundle_dir.glob("*.index.js"):
        try:
            text = chunk.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if STATUS_INTERVAL_MARKER in text:
            hits += 1
            continue
        if _STATUS_INTERVAL_OLD not in text:
            continue
        if dry_run:
            hits += 1
            continue
        bak = chunk.with_suffix(chunk.suffix + f".bak.{time.strftime('%Y%m%d%H%M%S')}")
        bak.write_text(text, encoding="utf-8")
        chunk.write_text(
            text.replace(_STATUS_INTERVAL_OLD, _STATUS_INTERVAL_NEW, 1),
            encoding="utf-8",
        )
        files.append(chunk)
        backups.append(bak)
        hits += 1
        logger.info("Patched statusLine interval in {}", chunk.name)
    return hits, files, backups

def strip_statusline_interval(
    bundle_dir: Path, dry_run: bool
) -> tuple[int, list[Path]]:
    files: list[Path] = []
    hits = 0
    for chunk in bundle_dir.glob("*.index.js"):
        try:
            text = chunk.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if _STATUS_INTERVAL_NEW not in text and STATUS_INTERVAL_MARKER not in text:
            continue
        if dry_run:
            hits += 1
            continue
        restored = text.replace(_STATUS_INTERVAL_NEW, _STATUS_INTERVAL_OLD, 1)
        if restored == text:
            continue
        chunk.write_text(restored, encoding="utf-8")
        files.append(chunk)
        hits += 1
    return hits, files

def patch_footer_keep(
    bundle_dir: Path, dry_run: bool
) -> tuple[int, list[Path], list[Path]]:
    """保留原生页脚，SC statusLine 只追加一行。"""
    files: list[Path] = []
    backups: list[Path] = []
    hits = 0
    for chunk in bundle_dir.glob("*.index.js"):
        try:
            text = chunk.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if FOOTER_KEEP_MARKER in text:
            hits += 1
            continue
        if _FOOTER_KEEP_OLD not in text:
            continue
        if dry_run:
            hits += 1
            continue
        bak = chunk.with_suffix(chunk.suffix + f".bak.{time.strftime('%Y%m%d%H%M%S')}")
        bak.write_text(text, encoding="utf-8")
        chunk.write_text(
            text.replace(_FOOTER_KEEP_OLD, _FOOTER_KEEP_NEW, 1),
            encoding="utf-8",
        )
        files.append(chunk)
        backups.append(bak)
        hits += 1
        logger.info("Patched prompt-footer keep-native in {}", chunk.name)
    return hits, files, backups

def strip_footer_keep(
    bundle_dir: Path, dry_run: bool
) -> tuple[int, list[Path]]:
    files: list[Path] = []
    hits = 0
    for chunk in bundle_dir.glob("*.index.js"):
        try:
            text = chunk.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if _FOOTER_KEEP_NEW not in text and FOOTER_KEEP_MARKER not in text:
            continue
        if dry_run:
            hits += 1
            continue
        restored = text.replace(_FOOTER_KEEP_NEW, _FOOTER_KEEP_OLD, 1)
        if restored == text:
            continue
        chunk.write_text(restored, encoding="utf-8")
        files.append(chunk)
        hits += 1
    return hits, files

def _inject_slash(bundle_dir: Path, dry_run: bool) -> tuple[int, list[Path], list[Path]]:
    """注入 / 更新 /sc slash（仅 pull|usage；异步 spawn）。"""
    files: list[Path] = []
    backups: list[Path] = []
    hits = 0
    for chunk in bundle_dir.glob("*.index.js"):
        try:
            text = chunk.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if _SLASH_ANCHOR not in text and 'ue.push({id:"sc"' not in text:
            continue
        # 已有旧注入：先剥掉再写入新版
        working = text
        if SLASH_MARKER in working or 'ue.push({id:"sc"' in working:
            start = working.find('ue.push({id:"sc"')
            end = working.find('ue.push({id:"plugin"', start) if start >= 0 else -1
            if start >= 0 and end > start:
                working = working[:start] + working[end:]
        if _SLASH_ANCHOR not in working:
            continue
        if _SLASH_INJECT in working:
            hits += 1
            continue
        hits += 1
        if dry_run:
            continue
        new_text = working.replace(_SLASH_ANCHOR, _SLASH_INJECT, 1)
        assert_js_syntax(chunk, new_text)
        bak = chunk.with_suffix(chunk.suffix + f".bak.{time.strftime('%Y%m%d%H%M%S')}")
        bak.write_text(text, encoding="utf-8")
        backups.append(bak)
        chunk.write_text(new_text, encoding="utf-8")
        files.append(chunk)
        logger.info("Injected /sc slash (pull|usage) into {}", chunk)
    return hits, files, backups


def _strip_slash(bundle_dir: Path, dry_run: bool) -> tuple[int, list[Path], list[Path]]:
    """移除历史 /sc slash 注入（rollback）。"""
    files: list[Path] = []
    backups: list[Path] = []
    hits = 0
    for chunk in slash_chunks(bundle_dir):
        text = chunk.read_text(encoding="utf-8", errors="ignore")
        if SLASH_MARKER not in text and 'ue.push({id:"sc"' not in text:
            continue
        start = text.find('ue.push({id:"sc"')
        end = text.find('ue.push({id:"plugin"', start) if start >= 0 else -1
        if start < 0 or end <= start:
            continue
        hits += 1
        if dry_run:
            continue
        new_text = text[:start] + text[end:]
        assert_js_syntax(chunk, new_text)
        bak = chunk.with_suffix(chunk.suffix + f".bak.{time.strftime('%Y%m%d%H%M%S')}")
        bak.write_text(text, encoding="utf-8")
        backups.append(bak)
        chunk.write_text(new_text, encoding="utf-8")
        files.append(chunk)
        logger.info("Removed /sc slash from {}", chunk)
    return hits, files, backups

def assert_js_syntax(path: Path, source: str) -> None:
    """用独立 checker + vm.Script 校验。

    勿用 ``node --check file``：对超大 webpack chunk 会误报。
    勿用 ``node -e code file``：Windows 上会把 file 再当入口解析。
    """
    node = find_cursor_agent_bundle()
    node_exe = Path("node")
    if node is not None:
        for name in ("node.exe", "node"):
            cand = node / name
            if cand.exists():
                node_exe = cand
                break
    tmp_path = None
    checker_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".js", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(source)
            tmp_path = tmp.name
        with tempfile.NamedTemporaryFile(
            "w", suffix=".js", delete=False, encoding="utf-8"
        ) as chk:
            chk.write(
                "const fs=require('fs');const vm=require('vm');\n"
                "try{new vm.Script(fs.readFileSync(process.argv[1],'utf8'));}\n"
                "catch(e){console.error(String(e&&e.message||e));process.exit(1)}\n"
            )
            checker_path = chk.name
        proc = subprocess.run(
            [str(node_exe), checker_path, tmp_path],
            capture_output=True,
            text=True,
            timeout=60,
        )
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)
        if checker_path:
            Path(checker_path).unlink(missing_ok=True)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip().splitlines()
        msg = err[0] if err else "unknown syntax error"
        raise RuntimeError(f"JS syntax check failed on {path.name}: {msg}")


def patch_boot_cmd(root: Path, dry_run: bool) -> tuple[bool, Optional[Path], Optional[Path]]:
    cmd = root / "cursor-agent.cmd"
    if not cmd.exists():
        return False, None, None
    text = cmd.read_text(encoding="utf-8", errors="ignore")
    boot = _BOOT_BLOCK if _BOOT_BLOCK.endswith("\n") else _BOOT_BLOCK + "\n"
    new_text = (
        "@echo off\r\n"
        "setlocal EnableExtensions\r\n"
        "\r\n"
        + boot.replace("\n", "\r\n")
        + "\r\n"
        + _CURSOR_AGENT_CMD_TAIL.replace("\n", "\r\n")
    )
    if text.replace("\r\n", "\n").strip() == new_text.replace("\r\n", "\n").strip():
        return True, None, None
    if dry_run:
        return True, None, None
    bak = cmd.with_suffix(cmd.suffix + f".bak.{time.strftime('%Y%m%d%H%M%S')}")
    bak.write_text(text, encoding="utf-8")
    write_script(cmd, new_text, crlf=True)
    logger.info("Patched cursor-agent.cmd boot+no-terminate → {}", cmd)
    return True, cmd, bak


def patch_launchers(root: Path, dry_run: bool) -> tuple[bool, list[Path], list[Path]]:
    """写入 ag.cmd / agent.cmd（no-terminate），与 cursor-agent.cmd 对齐。"""
    files: list[Path] = []
    backups: list[Path] = []
    changed = False
    for name in ("ag.cmd", "agent.cmd"):
        path = root / name
        if not path.exists():
            continue
        old = path.read_text(encoding="utf-8", errors="ignore")
        if old.replace("\r\n", "\n").strip() == _AG_CMD.strip():
            continue
        changed = True
        if dry_run:
            continue
        bak = path.with_suffix(path.suffix + f".bak.{time.strftime('%Y%m%d%H%M%S')}")
        bak.write_text(old, encoding="utf-8")
        backups.append(bak)
        write_script(path, _AG_CMD, crlf=True)
        files.append(path)
        logger.info("Patched {} no-terminate", name)
    return changed or bool(files), files, backups