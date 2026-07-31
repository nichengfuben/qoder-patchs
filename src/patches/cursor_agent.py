from __future__ import annotations

"""Cursor Agent：auth 热读 + 便携 sc 启动器补丁。

逆向 ``cursor-agent`` AuthStorage：
``getAccessToken`` / ``getRefreshToken`` / ``getApiKey`` / ``getAllCredentials``
默认命中内存缓存，外部改写 ``%APPDATA%\\Cursor\\auth.json`` 不生效。
本补丁去掉缓存短路，每次从磁盘 ``readAuthData``，配合 ``sc auto`` 热换号。

同时在安装根写入 ``sc.cmd`` / ``sc.ps1``，便于 ``/sc`` 与 PATH 调用。
"""

import time
from pathlib import Path
from typing import Optional

from loguru import logger

from core.patch_base import PatchBase, PatchMetadata, PatchResult, PatchStatus
from sc.paths import find_cursor_agent_bundle, find_cursor_agent_root

MARKER = "/*agentcli-hot-auth*/"

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


_SC_CMD = r"""@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%sc.ps1" %*
"""

_SC_PS1 = r"""param([Parameter(ValueFromRemainingArguments=$true)]$ArgsRest)
$ErrorActionPreference = "Stop"
# Prefer installed module; fall back to repo src if AGENTCLI_PATCHS_SRC set
if ($env:AGENTCLI_PATCHS_SRC) {
  $env:PYTHONPATH = $env:AGENTCLI_PATCHS_SRC
}
python -m sc @ArgsRest
exit $LASTEXITCODE
"""


class CursorAgentPatch(PatchBase):
    """Hot-reload auth.json + install portable ``sc`` launcher."""

    @property
    def metadata(self) -> PatchMetadata:
        return PatchMetadata(
            name="cursor-agent",
            display_name="Cursor Agent 热更新与 /sc 便携换号",
            description=(
                "去掉 cursor-agent AuthStorage 内存缓存短路，外部写入 auth.json 立即生效；"
                "在安装根部署 sc.cmd，配合 /sc pull|/sc auto 便携换号。"
                "config.json 与 auth.json 同级（%APPDATA%\\Cursor\\）。"
            ),
            version="1.0.0",
            author="nichengfuben",
            target_files=("index.js", "sc.cmd", "sc.ps1"),
            tags=("cursor-agent", "auth", "hot-reload", "sc"),
            reversible=True,
        )

    def _index_js(self, bundle_dir: Path) -> Path:
        return bundle_dir / "index.js"

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
        if hot_ok and sc_ok:
            return PatchStatus.APPLIED
        if hot_ok or sc_ok:
            return PatchStatus.PARTIAL
        return PatchStatus.NOT_APPLIED

    def _resolve_bundle(self, bundle_dir: Path) -> Optional[Path]:
        if (bundle_dir / "index.js").exists():
            return bundle_dir
        return find_cursor_agent_bundle()

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
        modified = content
        hits = 0
        for old, new in _REPLACEMENTS:
            if old in modified:
                modified = modified.replace(old, new, 1)
                hits += 1
            elif new in modified or MARKER in modified and old.split("){")[0] in modified:
                hits += 1  # already patched variant
        root = find_cursor_agent_root()
        files: list[Path] = []
        backups: list[Path] = []

        if dry_run:
            return PatchResult(
                status=PatchStatus.APPLIED if hits >= 1 else PatchStatus.FAILED,
                message=f"[dry-run] hot-auth hits={hits}, would install sc at {root}",
                patch_name=self.metadata.name,
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        if hits == 0 and MARKER not in content:
            return PatchResult(
                status=PatchStatus.FAILED,
                message="未匹配到 AuthStorage 缓存片段（cursor-agent 版本可能已变）",
                patch_name=self.metadata.name,
                duration_ms=int((time.monotonic() - start) * 1000),
                error="pattern miss",
            )

        if modified != content:
            bak = index.with_suffix(index.suffix + f".bak.{time.strftime('%Y%m%d%H%M%S')}")
            bak.write_text(content, encoding="utf-8")
            backups.append(bak)
            index.write_text(modified, encoding="utf-8")
            files.append(index)
            logger.info("Patched hot-auth in {}", index)

        if root is not None:
            cmd = root / "sc.cmd"
            ps1 = root / "sc.ps1"
            cmd.write_text(_SC_CMD, encoding="utf-8")
            ps1.write_text(_SC_PS1, encoding="utf-8")
            files.extend([cmd, ps1])

        return PatchResult(
            status=PatchStatus.APPLIED,
            message=f"hot-auth + sc 已应用 (hits={hits}, root={root})",
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
                message="[dry-run] would rollback hot-auth and remove sc.cmd",
                patch_name=self.metadata.name,
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        if restored != content:
            index.write_text(restored, encoding="utf-8")
            files.append(index)
        root = find_cursor_agent_root()
        if root:
            for name in ("sc.cmd", "sc.ps1"):
                p = root / name
                if p.exists():
                    p.unlink()
                    files.append(p)
        return PatchResult(
            status=PatchStatus.NOT_APPLIED,
            message="已回滚 hot-auth 并移除 sc 启动器",
            patch_name=self.metadata.name,
            files_modified=files,
            duration_ms=int((time.monotonic() - start) * 1000),
        )
