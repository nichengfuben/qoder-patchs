from __future__ import annotations

"""Cursor Agent：auth 热读 + Agent 内置 ``/sc`` slash + 便携 sc 启动器。

逆向 ``cursor-agent``：

1. AuthStorage ``getAccessToken`` 等命中内存缓存，外部改写 ``auth.json`` 不生效。
2. 交互 UI 的 slash 注册在 webpack chunk（如 ``5305.index.js``）的 ``ue.push({id:"mcp"...})``；
   仅写 ``sc.cmd`` 不会让 Agent 输入框里的 ``/sc`` 生效（只会落到技能模糊匹配）。

本补丁：去掉 auth 缓存短路；向 slash 表注入 ``/sc``；安装根写入 ``sc.cmd``/``sc.ps1``。
"""

import time
from pathlib import Path
from typing import Optional

from loguru import logger

from core.patch_base import PatchBase, PatchMetadata, PatchResult, PatchStatus
from sc.paths import find_cursor_agent_bundle, find_cursor_agent_root
from utils.paths import get_project_root

MARKER = "/*agentcli-hot-auth*/"
SLASH_MARKER = "/*agentcli-sc-slash*/"

# 原始短路缓存片段 → 强制读盘（保持 minify 风格）
_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (
        "getAccessToken(){return o(this,void 0,void 0,(function*(){var e;if(this.cachedAccessToken)return this.cachedAccessToken;const t=yield this.readAuthData();return(null==t?void 0:t.accessToken)?(this.cachedAccessToken=t.accessToken,this.cachedRefreshToken=null!==(e=t.refreshToken)&&void 0!==e?e:null,t.accessToken):void 0}))}",
        "getAccessToken(){return o(this,void 0,void 0,(function*(){var e;/*agentcli-hot-auth*/const t=yield this.readAuthData();return(null==t?void 0:t.accessToken)?(this.cachedAccessToken=t.accessToken,this.cachedRefreshToken=null!==(e=t.refreshToken)&&void 0!==e?e:null,t.accessToken):(this.cachedAccessToken=null,void 0)}))}",
    ),
    (
        "getRefreshToken(){return o(this,void 0,void 0,(function*(){var e;if(this.cachedRefreshToken)return this.cachedRefreshToken;const t=yield this.readAuthData();return(null==t?void 0:t.refreshToken)?(this.cachedAccessToken=null!==(e=t.accessToken)&&void 0!==e?e:null,this.cachedRefreshToken=t.refreshToken,t.refreshToken):void 0}))}",
        "getRefreshToken(){return o(this,void 0,void 0,(function*(){var e;/*agentcli-hot-auth*/const t=yield this.readAuthData();return(null==t?void 0:t.refreshToken)?(this.cachedAccessToken=null!==(e=t.accessToken)&&void 0!==e?e:null,this.cachedRefreshToken=t.refreshToken,t.refreshToken):(this.cachedRefreshToken=null,void 0)}))}",
    ),
    (
        "getApiKey(){return o(this,void 0,void 0,(function*(){if(this.cachedApiKey)return this.cachedApiKey;const e=yield this.readAuthData();return(null==e?void 0:e.apiKey)?(this.cachedApiKey=e.apiKey,e.apiKey):void 0}))}",
        "getApiKey(){return o(this,void 0,void 0,(function*(){/*agentcli-hot-auth*/const e=yield this.readAuthData();return(null==e?void 0:e.apiKey)?(this.cachedApiKey=e.apiKey,e.apiKey):(this.cachedApiKey=null,void 0)}))}",
    ),
)

# 紧挨 /mcp 之后、/plugin 之前注入 /sc（参数名 ui 避免遮蔽 webpack require `n`）
_SLASH_ANCHOR = 'ue.push({id:"plugin",title:"Plugin"'
_SLASH_INJECT = (
    'ue.push({id:"sc",title:"SC",'
    + SLASH_MARKER
    + 'autoExecuteOnAccept:!0,description:"Portable Star Cursor switch (pull/usage/token/status/addkey/auto)",'
    'ghostText:"[pull|usage|token|status|addkey|auto|help] [...]",'
    'boostedAlts:["starcursor","switch-account"],'
    'args:[{id:"subcommand",required:!1},{id:"rest",required:!1}],'
    "getArgSuggestions:(e,t)=>{"
    'const q=(t[0]||"").trim().toLowerCase();'
    "if(t.length<=1){"
    'const opts=[{value:"pull",description:"Pull token → auth.json",autoExecuteOnAccept:!0},'
    '{value:"usage",description:"Show usage",autoExecuteOnAccept:!0},'
    '{value:"token",description:"Show local token",autoExecuteOnAccept:!0},'
    '{value:"status",description:"Show status",autoExecuteOnAccept:!0},'
    '{value:"addkey",description:"Add API key"},'
    '{value:"auto",description:"Background poll / auto stop"},'
    '{value:"help",description:"Show help",autoExecuteOnAccept:!0}];'
    "return q?opts.filter((e=>e.value.startsWith(q))):opts}"
    "return[]},"
    "run:(e,t,ui)=>se(this,void 0,void 0,(function*(){"
    "var o,r;null===(o=ui.clearInput)||void 0===o||o.call(ui);"
    'let s="",i=1;try{'
    'const cp=n("node:child_process"),path=n("node:path"),fs=n("node:fs");'
    'const root=process.env.LOCALAPPDATA?path.join(process.env.LOCALAPPDATA,"cursor-agent"):"";'
    'const scCmd=root?path.join(root,"sc.cmd"):"";'
    "const args=t.slice();let proc;"
    "if(scCmd&&fs.existsSync(scCmd))"
    "proc=cp.spawnSync(scCmd,args,{encoding:\"utf8\",shell:!0,env:process.env,timeout:12e4});"
    "else proc=cp.spawnSync(process.env.AGENTCLI_PYTHON||\"python\","
    '["-m","sc"].concat(args),{encoding:"utf8",shell:!1,env:process.env,timeout:12e4});'
    's=((proc.stdout||"")+(proc.stderr||"")).trim()||`(exit ${null!=proc.status?proc.status:"?"})`;'
    "i=null!=proc.status?proc.status:1"
    "}catch(e){s=String(null!=e.message?e.message:e);i=1}"
    "const lines=s.split(/\\r?\\n/).map((e=>[{text:e,color:i?\"red\":\"green\"}]));"
    "null===(r=ui.print)||void 0===r||r.call(ui,lines.length?lines:[[{text:\"(no output)\",dim:!0}]],"
    "{minLingerMs:8e3}),ui.insertText(''))})),"
    + _SLASH_ANCHOR
)

_SC_CMD = r"""@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%sc.ps1" %*
"""


def _sc_ps1(src_dir: Path) -> str:
    # 安装时写入绝对 PYTHONPATH，保证未 pip install 也能 python -m sc
    src = str(src_dir).replace("'", "''")
    return f"""param([Parameter(ValueFromRemainingArguments=$true)]$ArgsRest)
$ErrorActionPreference = "Stop"
$env:PYTHONPATH = if ($env:AGENTCLI_PATCHS_SRC) {{ $env:AGENTCLI_PATCHS_SRC }} else {{ '{src}' }}
$py = if ($env:AGENTCLI_PYTHON) {{ $env:AGENTCLI_PYTHON }} else {{ 'python' }}
& $py -m sc @ArgsRest
exit $LASTEXITCODE
"""


class CursorAgentPatch(PatchBase):
    """Hot-reload auth.json + inject Agent ``/sc`` slash + install portable launcher."""

    @property
    def metadata(self) -> PatchMetadata:
        return PatchMetadata(
            name="cursor-agent",
            display_name="Cursor Agent 热更新与 /sc 便携换号",
            description=(
                "去掉 AuthStorage 内存缓存；向 Agent slash 面板注入 /sc；"
                "安装根部署 sc.cmd。config.json 与 auth.json 同级（%APPDATA%\\Cursor\\）。"
            ),
            version="1.1.0",
            author="nichengfuben",
            target_files=("index.js", "*.index.js", "sc.cmd", "sc.ps1"),
            tags=("cursor-agent", "auth", "hot-reload", "sc", "slash"),
            reversible=True,
        )

    def _index_js(self, bundle_dir: Path) -> Path:
        return bundle_dir / "index.js"

    def _slash_chunks(self, bundle_dir: Path) -> list[Path]:
        """含 mcp→plugin slash 锚点的 webpack chunk。"""
        hits: list[Path] = []
        for path in bundle_dir.glob("*.index.js"):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if 'ue.push({id:"mcp",title:"MCP"' in text or SLASH_MARKER in text:
                hits.append(path)
        return hits

    def check(self, bundle_dir: Path) -> PatchStatus:
        target = self._resolve_bundle(bundle_dir)
        if target is None:
            return PatchStatus.UNKNOWN
        index = self._index_js(target)
        if not index.exists():
            return PatchStatus.UNKNOWN
        text = index.read_text(encoding="utf-8", errors="ignore")
        root = find_cursor_agent_root()
        sc_ok = bool(root and (root / "sc.cmd").exists())
        hot_ok = MARKER in text
        slash_ok = any(
            SLASH_MARKER in p.read_text(encoding="utf-8", errors="ignore")
            for p in self._slash_chunks(target)
        )
        if hot_ok and sc_ok and slash_ok:
            return PatchStatus.APPLIED
        if hot_ok or sc_ok or slash_ok:
            return PatchStatus.PARTIAL
        return PatchStatus.NOT_APPLIED

    def _resolve_bundle(self, bundle_dir: Optional[Path] = None) -> Optional[Path]:
        if bundle_dir is not None and (bundle_dir / "index.js").exists():
            return bundle_dir
        return find_cursor_agent_bundle()

    def _patch_hot_auth(self, index: Path, dry_run: bool) -> tuple[int, Optional[Path], Optional[Path]]:
        content = index.read_text(encoding="utf-8", errors="ignore")
        modified = content
        hits = 0
        for old, new in _REPLACEMENTS:
            if old in modified:
                modified = modified.replace(old, new, 1)
                hits += 1
            elif MARKER in modified and old.split("){")[0] in modified:
                hits += 1
        if dry_run or modified == content:
            return hits, None, None
        bak = index.with_suffix(index.suffix + f".bak.{time.strftime('%Y%m%d%H%M%S')}")
        bak.write_text(content, encoding="utf-8")
        index.write_text(modified, encoding="utf-8")
        return hits, index, bak

    def _patch_slash(self, bundle_dir: Path, dry_run: bool) -> tuple[int, list[Path], list[Path]]:
        files: list[Path] = []
        backups: list[Path] = []
        hits = 0
        for chunk in self._slash_chunks(bundle_dir):
            text = chunk.read_text(encoding="utf-8", errors="ignore")
            if SLASH_MARKER in text:
                hits += 1
                continue
            if _SLASH_ANCHOR not in text:
                continue
            hits += 1
            if dry_run:
                continue
            bak = chunk.with_suffix(chunk.suffix + f".bak.{time.strftime('%Y%m%d%H%M%S')}")
            bak.write_text(text, encoding="utf-8")
            backups.append(bak)
            chunk.write_text(text.replace(_SLASH_ANCHOR, _SLASH_INJECT, 1), encoding="utf-8")
            files.append(chunk)
            logger.info("Patched /sc slash in {}", chunk)
        return hits, files, backups

    def apply(self, bundle_dir: Path, dry_run: bool = False) -> PatchResult:
        start = time.monotonic()
        target = self._resolve_bundle(bundle_dir)
        if target is None:
            return PatchResult(
                status=PatchStatus.FAILED,
                message="未找到 cursor-agent version 目录（index.js）",
                patch_name=self.metadata.name,
                duration_ms=int((time.monotonic() - start) * 1000),
                error="bundle not found",
            )
        index = self._index_js(target)
        content = index.read_text(encoding="utf-8", errors="ignore")
        hot_hits, hot_file, hot_bak = self._patch_hot_auth(index, dry_run=True)
        slash_hits, _, _ = self._patch_slash(target, dry_run=True)
        root = find_cursor_agent_root()

        if dry_run:
            return PatchResult(
                status=PatchStatus.APPLIED if (hot_hits >= 1 or slash_hits >= 1) else PatchStatus.FAILED,
                message=(
                    f"[dry-run] hot-auth hits={hot_hits}, slash hits={slash_hits}, "
                    f"would install sc at {root}"
                ),
                patch_name=self.metadata.name,
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        if hot_hits == 0 and MARKER not in content and slash_hits == 0:
            return PatchResult(
                status=PatchStatus.FAILED,
                message="未匹配到 AuthStorage / slash 锚点（cursor-agent 版本可能已变）",
                patch_name=self.metadata.name,
                duration_ms=int((time.monotonic() - start) * 1000),
                error="pattern miss",
            )

        files: list[Path] = []
        backups: list[Path] = []
        hot_hits, hot_file, hot_bak = self._patch_hot_auth(index, dry_run=False)
        if hot_file:
            files.append(hot_file)
        if hot_bak:
            backups.append(hot_bak)
            logger.info("Patched hot-auth in {}", index)

        slash_hits, slash_files, slash_baks = self._patch_slash(target, dry_run=False)
        files.extend(slash_files)
        backups.extend(slash_baks)

        if root is not None:
            src = get_project_root() / "src"
            cmd = root / "sc.cmd"
            ps1 = root / "sc.ps1"
            cmd.write_text(_SC_CMD, encoding="utf-8")
            ps1.write_text(_sc_ps1(src), encoding="utf-8")
            files.extend([cmd, ps1])

        return PatchResult(
            status=PatchStatus.APPLIED,
            message=(
                f"hot-auth + /sc slash + sc 已应用 "
                f"(hot={hot_hits}, slash={slash_hits}, root={root})"
            ),
            patch_name=self.metadata.name,
            files_modified=files,
            backups_created=backups,
            duration_ms=int((time.monotonic() - start) * 1000),
        )

    def rollback(self, bundle_dir: Path, dry_run: bool = False) -> PatchResult:
        start = time.monotonic()
        target = self._resolve_bundle(bundle_dir)
        if target is None:
            return PatchResult(
                status=PatchStatus.FAILED,
                message="未找到 cursor-agent bundle",
                patch_name=self.metadata.name,
                duration_ms=int((time.monotonic() - start) * 1000),
                error="missing",
            )
        index = self._index_js(target)
        content = index.read_text(encoding="utf-8", errors="ignore")
        restored = content
        for old, new in _REPLACEMENTS:
            if new in restored:
                restored = restored.replace(new, old, 1)
        files: list[Path] = []
        if dry_run:
            return PatchResult(
                status=PatchStatus.NOT_APPLIED,
                message="[dry-run] would rollback hot-auth, /sc slash, and sc.cmd",
                patch_name=self.metadata.name,
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        if restored != content:
            index.write_text(restored, encoding="utf-8")
            files.append(index)
        for chunk in self._slash_chunks(target):
            text = chunk.read_text(encoding="utf-8", errors="ignore")
            if SLASH_MARKER not in text or _SLASH_INJECT not in text:
                # 容错：仅按 marker 包围块粗回滚
                if SLASH_MARKER in text and _SLASH_ANCHOR in text:
                    # 已注入形态：整段 inject 替换回 anchor
                    if _SLASH_INJECT in text:
                        chunk.write_text(
                            text.replace(_SLASH_INJECT, _SLASH_ANCHOR, 1), encoding="utf-8"
                        )
                        files.append(chunk)
                continue
            chunk.write_text(text.replace(_SLASH_INJECT, _SLASH_ANCHOR, 1), encoding="utf-8")
            files.append(chunk)
        root = find_cursor_agent_root()
        if root:
            for name in ("sc.cmd", "sc.ps1"):
                p = root / name
                if p.exists():
                    p.unlink()
                    files.append(p)
        return PatchResult(
            status=PatchStatus.NOT_APPLIED,
            message="已回滚 hot-auth、/sc slash 并移除 sc 启动器",
            patch_name=self.metadata.name,
            files_modified=files,
            duration_ms=int((time.monotonic() - start) * 1000),
        )
