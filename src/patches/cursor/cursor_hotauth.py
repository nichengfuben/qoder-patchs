from __future__ import annotations

"""Cursor Agent hot-auth replacements and markers."""

import os
import shutil
from pathlib import Path
from typing import Optional

from patches.cursor.cursor_chunks import (
    _AGENTCLI_UPGRADE_GUARD,
    _AGENTCLI_UPGRADE_GUARD_V3,
    _FOOTER_KEEP_NEW,
    _FOOTER_KEEP_OLD,
    _SLASH_ANCHOR,
    _SLASH_INJECT,
    _STATUS_INTERVAL_NEW,
    _STATUS_INTERVAL_OLD,
)
from patches.cursor.cursor_repls import _REPLACEMENTS
from utils.cursor_nudge import NUDGE_MARKER

_ACTION_REQUIRED_OLD = 'if(void 0!==n&&""!==n)return new R(j(e,u),n,d);'
_ACTION_REQUIRED_NEW = (
    'if(void 0!==n&&""!==n){const _r=new R(j(e,u),n,d);'
    'if("upgrade"===n||"payment"===n){try{_agentcliWaitAuthUpgrade(_r)}catch(_e){}}return _r}'
)
_UPGRADE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (_AGENTCLI_UPGRADE_GUARD_V3, _AGENTCLI_UPGRADE_GUARD),
    (_ACTION_REQUIRED_OLD, _ACTION_REQUIRED_NEW),
)
BEARER_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (
        'function se(e){return t=>n=>ne(this,void 0,void 0,(function*(){const r=yield e.getAccessToken();if(!r)throw new Error("No access token found");n.header.set("authorization",`Bearer ${r}`);',
        'function se(e){return t=>n=>ne(this,void 0,void 0,(function*(){var r=yield e.getAccessToken();'
        '/*agentcli-hot-auth*/try{const _fs=(process.getBuiltinModule&&(process.getBuiltinModule("node:fs")||process.getBuiltinModule("fs")))||require("node:fs"),'
        '_path=(process.getBuiltinModule&&(process.getBuiltinModule("node:path")||process.getBuiltinModule("path")))||require("node:path"),'
        '_os=(process.getBuiltinModule&&(process.getBuiltinModule("node:os")||process.getBuiltinModule("os")))||require("node:os");'
        'const _dir="win32"===process.platform?_path.join(process.env.APPDATA||_path.join(_os.homedir(),"AppData","Roaming"),"Cursor"):_path.join(_os.homedir(),".cursor");'
        'const _j=JSON.parse(_fs.readFileSync(_path.join(_dir,"auth.json"),"utf8"));if(_j&&_j.accessToken)r=_j.accessToken;'
        '_fs.writeFileSync(_path.join(_dir,"agentcli-last-bearer.json"),JSON.stringify({sub:JSON.parse(Buffer.from(String(r).split(".")[1],"base64").toString()).sub,ts:Date.now(),pid:process.pid,via:"se"}))}catch(_e){}'
        'if(!r)throw new Error("No access token found");n.header.set("authorization",`Bearer ${r}`);',
    ),
    (
        'const r=yield e.credentialManager.getAccessToken();return r&&n.header.set("authorization",`Bearer ${r}`),t(n)',
        'var r=yield e.credentialManager.getAccessToken();'
        '/*agentcli-hot-auth*/try{const _fs=(process.getBuiltinModule&&(process.getBuiltinModule("node:fs")||process.getBuiltinModule("fs")))||require("node:fs"),'
        '_path=(process.getBuiltinModule&&(process.getBuiltinModule("node:path")||process.getBuiltinModule("path")))||require("node:path"),'
        '_os=(process.getBuiltinModule&&(process.getBuiltinModule("node:os")||process.getBuiltinModule("os")))||require("node:os");'
        'const _dir="win32"===process.platform?_path.join(process.env.APPDATA||_path.join(_os.homedir(),"AppData","Roaming"),"Cursor"):_path.join(_os.homedir(),".cursor");'
        'const _j=JSON.parse(_fs.readFileSync(_path.join(_dir,"auth.json"),"utf8"));if(_j&&_j.accessToken)r=_j.accessToken;'
        '_fs.writeFileSync(_path.join(_dir,"agentcli-last-bearer.json"),JSON.stringify({sub:JSON.parse(Buffer.from(String(r).split(".")[1],"base64").toString()).sub,ts:Date.now(),pid:process.pid,via:"cm-t"}))}catch(_e){}'
        'return r&&n.header.set("authorization",`Bearer ${r}`),t(n)',
    ),
    (
        'const s=yield e.credentialManager.getAccessToken();return s&&n.header.set("authorization",`Bearer ${s}`),(0,r._5)(n.header),t(n)',
        'var s=yield e.credentialManager.getAccessToken();'
        '/*agentcli-hot-auth*/try{const _fs=(process.getBuiltinModule&&(process.getBuiltinModule("node:fs")||process.getBuiltinModule("fs")))||require("node:fs"),'
        '_path=(process.getBuiltinModule&&(process.getBuiltinModule("node:path")||process.getBuiltinModule("path")))||require("node:path"),'
        '_os=(process.getBuiltinModule&&(process.getBuiltinModule("node:os")||process.getBuiltinModule("os")))||require("node:os");'
        'const _dir="win32"===process.platform?_path.join(process.env.APPDATA||_path.join(_os.homedir(),"AppData","Roaming"),"Cursor"):_path.join(_os.homedir(),".cursor");'
        'const _j=JSON.parse(_fs.readFileSync(_path.join(_dir,"auth.json"),"utf8"));if(_j&&_j.accessToken)s=_j.accessToken;'
        '_fs.writeFileSync(_path.join(_dir,"agentcli-last-bearer.json"),JSON.stringify({sub:JSON.parse(Buffer.from(String(s).split(".")[1],"base64").toString()).sub,ts:Date.now(),pid:process.pid,via:"cm-s"}))}catch(_e){}'
        'return s&&n.header.set("authorization",`Bearer ${s}`),(0,r._5)(n.header),t(n)',
    ),
    (
        'const r=yield e.credentialManager.getAccessToken();return r&&n.header.set("authorization",`Bearer ${r}`),o(n.header),t(n)',
        'var r=yield e.credentialManager.getAccessToken();'
        '/*agentcli-hot-auth*/try{const _fs=(process.getBuiltinModule&&(process.getBuiltinModule("node:fs")||process.getBuiltinModule("fs")))||require("node:fs"),'
        '_path=(process.getBuiltinModule&&(process.getBuiltinModule("node:path")||process.getBuiltinModule("path")))||require("node:path"),'
        '_os=(process.getBuiltinModule&&(process.getBuiltinModule("node:os")||process.getBuiltinModule("os")))||require("node:os");'
        'const _dir="win32"===process.platform?_path.join(process.env.APPDATA||_path.join(_os.homedir(),"AppData","Roaming"),"Cursor"):_path.join(_os.homedir(),".cursor");'
        'const _j=JSON.parse(_fs.readFileSync(_path.join(_dir,"auth.json"),"utf8"));if(_j&&_j.accessToken)r=_j.accessToken;'
        '_fs.writeFileSync(_path.join(_dir,"agentcli-last-bearer.json"),JSON.stringify({sub:JSON.parse(Buffer.from(String(r).split(".")[1],"base64").toString()).sub,ts:Date.now(),pid:process.pid,via:"cm-o"}))}catch(_e){}'
        'return r&&n.header.set("authorization",`Bearer ${r}`),o(n.header),t(n)',
    ),
)

MARKER = "/*agentcli-hot-auth*/"
DISK_MARKER = "/*agentcli-hot-auth-disk*/"
SLASH_MARKER = "/*agentcli-sc-slash*/"
BOOT_MARKER = "REM agentcli-sc-auto-boot"
STATUS_INTERVAL_MARKER = "/*agentcli-status-interval*/"
FOOTER_KEEP_MARKER = "/*agentcli-footer-keep*/"
EPHEMERAL_NULL_MARKER = "ephemeralToken:null/*agentcli-hot-auth*/"


def uichunk_texts(target: Path) -> list[str]:
    texts: list[str] = []
    for p in target.glob("*.index.js"):
        if not p.is_file():
            continue
        try:
            texts.append(p.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
    return texts


def optional_uichunk_ok(texts: list[str], marker: str, old: str) -> bool:
    if any(marker in t for t in texts):
        return True
    return not any(old in t for t in texts)


def nudge_flag_ok(chunks: list[str]) -> bool:
    # continue-nudge 已停用：残留注入视为未达预期（重新 apply 会 strip）
    return not any(NUDGE_MARKER in t for t in chunks)

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
    for old, new in (*_REPLACEMENTS, *BEARER_REPLACEMENTS, *_UPGRADE_REPLACEMENTS):
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
