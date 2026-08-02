from __future__ import annotations

"""Legacy continue-nudge strip/inject (nudge 已停用，仅保留回滚/清理)。"""

import time
from pathlib import Path

from loguru import logger

NUDGE_MARKER = "/*agentcli-sc-nudge*/"
_NUDGE_ANCHOR = ",yr=(0,$.eg)(e,We,br,Wo.inHistory,_o),wr="
_NUDGE_EFFECT = (
    NUDGE_MARKER
    + "_agentcliNudge=(0,c.useEffect)((()=>{const _iv=setInterval((()=>{try{"
    'const _fs=(process.getBuiltinModule&&(process.getBuiltinModule("node:fs")'
    '||process.getBuiltinModule("fs")))||require("node:fs");'
    'const _path=(process.getBuiltinModule&&(process.getBuiltinModule("node:path")'
    '||process.getBuiltinModule("path")))||require("node:path");'
    'const _os=(process.getBuiltinModule&&(process.getBuiltinModule("node:os")'
    '||process.getBuiltinModule("os")))||require("node:os");'
    'const _p=_path.join(_os.homedir(),".cursor","sc_nudge.json");'
    "if(!_fs.existsSync(_p))return;"
    'const _j=JSON.parse(_fs.readFileSync(_p,"utf8"));'
    'if(!_j||"continue"!==_j.action)return;'
    "const _ts=Number(_j.ts||0);"
    "if(!_ts||Date.now()-_ts>12e4)return void _fs.unlinkSync(_p);"
    'if(null==br||"function"!=typeof br.submitMessage)return;'
    'const _t=String(_j.text||"继续");'
    "br.submitMessage(_t);"
    "try{_fs.unlinkSync(_p)}catch(_e){}"
    "}catch(_e){}}),1e3);return()=>clearInterval(_iv)}),[br])"
)
_NUDGE_INJECT = (
    ",yr=(0,$.eg)(e,We,br,Wo.inHistory,_o)," + _NUDGE_EFFECT + ",wr="
)


def _nudge_strip_region(text: str) -> str:
    if NUDGE_MARKER not in text:
        return text
    start = text.find(",yr=(0,$.eg)(e,We,br,Wo.inHistory,_o)," + NUDGE_MARKER)
    if start >= 0:
        end = text.find(",wr=", start)
        if end > start:
            return text[:start] + _NUDGE_ANCHOR + text[end + len(",wr=") :]
    start = text.find(",yr=(0,$.eg)(e,We,br,Wo.inHistory,_o);" + NUDGE_MARKER)
    if start >= 0:
        end = text.find(";wr=", start)
        if end > start:
            return text[:start] + _NUDGE_ANCHOR + text[end + len(";wr=") :]
    legacy = "," + NUDGE_MARKER
    start = text.find(legacy)
    if start < 0:
        start = text.find(NUDGE_MARKER)
    end = text.find(",yr=(0,$.eg)(e,We,br,Wo.inHistory,_o)", start) if start >= 0 else -1
    if start >= 0 and end > start:
        return text[:start] + text[end:]
    return text


def inject_nudge(bundle_dir, dry_run: bool = False):
    files: list = []
    backups: list = []
    hits = 0
    root = Path(bundle_dir)
    for chunk in root.glob("*.index.js"):
        try:
            text = chunk.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if _NUDGE_ANCHOR not in text and NUDGE_MARKER not in text:
            continue
        working = _nudge_strip_region(text)
        if _NUDGE_ANCHOR not in working:
            continue
        if _NUDGE_INJECT in working:
            hits += 1
            continue
        hits += 1
        if dry_run:
            continue
        from patches.cursor.cursor_patchops import assert_js_syntax

        new_text = working.replace(_NUDGE_ANCHOR, _NUDGE_INJECT, 1)
        assert_js_syntax(chunk, new_text)
        bak = chunk.with_suffix(chunk.suffix + f".bak.{time.strftime('%Y%m%d%H%M%S')}")
        bak.write_text(text, encoding="utf-8")
        backups.append(bak)
        chunk.write_text(new_text, encoding="utf-8")
        files.append(chunk)
        logger.info("Injected sc continue-nudge into {}", chunk)
    return hits, files, backups


def strip_nudge(bundle_dir, dry_run: bool = False):
    files: list = []
    backups: list = []
    hits = 0
    for chunk in Path(bundle_dir).glob("*.index.js"):
        try:
            text = chunk.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if NUDGE_MARKER not in text:
            continue
        new_text = _nudge_strip_region(text)
        if new_text == text:
            continue
        hits += 1
        if dry_run:
            continue
        from patches.cursor.cursor_patchops import assert_js_syntax

        assert_js_syntax(chunk, new_text)
        bak = chunk.with_suffix(chunk.suffix + f".bak.{time.strftime('%Y%m%d%H%M%S')}")
        bak.write_text(text, encoding="utf-8")
        backups.append(bak)
        chunk.write_text(new_text, encoding="utf-8")
        files.append(chunk)
        logger.info("Removed sc continue-nudge from {}", chunk)
    return hits, files, backups
