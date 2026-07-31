from __future__ import annotations

"""Cursor Agent hot-auth replacements and markers."""

import os
import shutil
from pathlib import Path
from typing import Optional

from patches.cursor.cursor_chunks import (
    _FOOTER_KEEP_NEW, _FOOTER_KEEP_OLD, _SLASH_ANCHOR, _SLASH_INJECT,
    _STATUS_INTERVAL_NEW, _STATUS_INTERVAL_OLD,
)
from patches.cursor.cursor_repls import _REPLACEMENTS

MARKER = "/*agentcli-hot-auth*/"
DISK_MARKER = "/*agentcli-hot-auth-disk*/"
SLASH_MARKER = "/*agentcli-sc-slash*/"
BOOT_MARKER = "REM agentcli-sc-auto-boot"
STATUS_INTERVAL_MARKER = "/*agentcli-status-interval*/"
FOOTER_KEEP_MARKER = "/*agentcli-footer-keep*/"
EPHEMERAL_NULL_MARKER = "ephemeralToken:null/*agentcli-hot-auth*/"

_COMPILE_CACHE_OLD = (
    "## Enable Node.js compile cache for faster CLI startup (requires Node.js >= 22.1.0)\n"
    "## Cache is automatically invalidated when source files change\n"
    "if (-not $env:NODE_COMPILE_CACHE) {\n"
    '    $env:NODE_COMPILE_CACHE = "$env:LOCALAPPDATA\\cursor-compile-cache"\n'
    "}"
)
_COMPILE_CACHE_NEW = (
    "## agentcli-hot-auth: disable NODE_COMPILE_CACHE so index.js patches always load\n"
    "Remove-Item Env:NODE_COMPILE_CACHE -ErrorAction SilentlyContinue\n"
)


def apply_hot_auth_replacements(content: str) -> tuple[str, int]:
    modified = content
    hits = 0
    for old, new in _REPLACEMENTS:
        if old in modified:
            modified = modified.replace(old, new, 1)
            hits += 1
        elif new in modified:
            hits += 1
    return modified, hits


def clear_node_compile_cache() -> Optional[Path]:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    cache = Path(local) / "cursor-compile-cache"
    if cache.is_dir():
        shutil.rmtree(cache, ignore_errors=True)
        return cache
    return None
