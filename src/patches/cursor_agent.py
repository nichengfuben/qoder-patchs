from __future__ import annotations

"""Cursor Agent：auth 热读 + 启动自动 sc auto + statusline（无 /sc slash）。

逆向要点：
1. AuthStorage 内存缓存 → 强制每次 readAuthData。
2. 进入 agent 时由 cursor-agent.cmd 引导后台 ``sc auto``（换号监测）。
3. 不再向 slash 面板注入 /sc。
"""

import json
import shutil
import time
from pathlib import Path
from typing import Optional

from loguru import logger

from core.patch_base import PatchBase, PatchMetadata, PatchResult, PatchStatus
from sc.cli_config import merge_status_line
from sc.paths import config_json_path, find_cursor_agent_bundle, find_cursor_agent_root
from utils.paths import get_project_root

MARKER = "/*agentcli-hot-auth*/"
SLASH_MARKER = "/*agentcli-sc-slash*/"
BOOT_MARKER = "REM agentcli-sc-auto-boot"

# 原始短路缓存片段 → 强制读盘
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

_BOOT_BLOCK = f"""{BOOT_MARKER}
REM Start sc auto (detached) before launching agent UI
if exist "%~dp0sc.cmd" start "" /B "%~dp0sc.cmd" auto
"""

_SC_CMD = r"""@echo off
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set "SCRIPT_DIR=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%sc.ps1" %*
"""

_SC_STATUSLINE_CMD = r"""@echo off
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set "SCRIPT_DIR=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%sc.ps1" statusline
"""

# client.py 旁默认配置路径（复制到 %APPDATA%\Cursor\config.json）
_CLIENT_CONFIG_CANDIDATES = (
    Path(r"X:\Project\Common\Common\config.json"),
    Path(r"X:\Project\Common\config.json"),
)


def _sc_ps1(src_dir: Path) -> str:
    src = str(src_dir).replace("'", "''")
    return f"""param([Parameter(ValueFromRemainingArguments=$true)]$ArgsRest)
$ErrorActionPreference = "Stop"
try {{ chcp 65001 | Out-Null }} catch {{}}
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONPATH = if ($env:AGENTCLI_PATCHS_SRC) {{ $env:AGENTCLI_PATCHS_SRC }} else {{ '{src}' }}
$py = if ($env:AGENTCLI_PYTHON) {{ $env:AGENTCLI_PYTHON }} else {{ 'python' }}
& $py -X utf8 -m sc @ArgsRest
exit $LASTEXITCODE
"""


def find_client_config() -> Optional[Path]:
    for p in _CLIENT_CONFIG_CANDIDATES:
        if p.is_file():
            return p
    return None


def ensure_sc_config_from_client(*, force: bool = False) -> Optional[Path]:
    """把 client.py 同目录 config.json 复制到与 auth.json 同级。"""
    src = find_client_config()
    if src is None:
        return None
    dst = config_json_path()
    if dst.exists() and not force:
        # 已有配置：若 api_keys 为空则仍覆盖
        try:
            cur = json.loads(dst.read_text(encoding="utf-8"))
            if cur.get("api_keys"):
                return dst
        except Exception:
            pass
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    logger.info("Copied SC config {} → {}", src, dst)
    return dst


class CursorAgentPatch(PatchBase):
    """Hot-reload auth + auto-boot sc auto + statusline（无 slash）。"""

    @property
    def metadata(self) -> PatchMetadata:
        return PatchMetadata(
            name="cursor-agent",
            display_name="Cursor Agent 热更新与自动换号",
            description=(
                "去掉 AuthStorage 内存缓存；启动 agent 时自动后台 sc auto；"
                "安装 statusline；config 与 auth.json 同级。"
            ),
            version="2.0.0",
            author="nichengfuben",
            target_files=(
                "index.js",
                "cursor-agent.cmd",
                "sc.cmd",
                "sc.ps1",
                "sc-statusline.cmd",
            ),
            tags=("cursor-agent", "auth", "hot-reload", "sc", "auto", "statusline"),
            reversible=True,
        )

    def _index_js(self, bundle_dir: Path) -> Path:
        return bundle_dir / "index.js"

    def _slash_chunks(self, bundle_dir: Path) -> list[Path]:
        hits: list[Path] = []
        for path in bundle_dir.glob("*.index.js"):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if SLASH_MARKER in text or 'ue.push({id:"sc"' in text:
                hits.append(path)
        return hits

    def _resolve_bundle(self, bundle_dir: Optional[Path] = None) -> Optional[Path]:
        if bundle_dir is not None and (bundle_dir / "index.js").exists():
            return bundle_dir
        return find_cursor_agent_bundle()

    def check(self, bundle_dir: Path) -> PatchStatus:
        target = self._resolve_bundle(bundle_dir)
        if target is None:
            return PatchStatus.UNKNOWN
        index = self._index_js(target)
        if not index.exists():
            return PatchStatus.UNKNOWN
        text = index.read_text(encoding="utf-8", errors="ignore")
        root = find_cursor_agent_root()
        sc_ok = bool(root and (root / "sc.cmd").exists() and (root / "sc-statusline.cmd").exists())
        hot_ok = MARKER in text
        boot_ok = False
        if root is not None:
            boot_cmd = root / "cursor-agent.cmd"
            if boot_cmd.exists():
                boot_ok = BOOT_MARKER in boot_cmd.read_text(encoding="utf-8", errors="ignore")
        slash_gone = len(self._slash_chunks(target)) == 0
        if hot_ok and sc_ok and boot_ok and slash_gone:
            return PatchStatus.APPLIED
        if hot_ok or sc_ok or boot_ok:
            return PatchStatus.PARTIAL
        return PatchStatus.NOT_APPLIED

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

    def _strip_slash(self, bundle_dir: Path, dry_run: bool) -> tuple[int, list[Path], list[Path]]:
        """移除历史 /sc slash 注入。"""
        files: list[Path] = []
        backups: list[Path] = []
        hits = 0
        for chunk in self._slash_chunks(bundle_dir):
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
            self._assert_js_syntax(chunk, new_text)
            bak = chunk.with_suffix(chunk.suffix + f".bak.{time.strftime('%Y%m%d%H%M%S')}")
            bak.write_text(text, encoding="utf-8")
            backups.append(bak)
            chunk.write_text(new_text, encoding="utf-8")
            files.append(chunk)
            logger.info("Removed /sc slash from {}", chunk)
        return hits, files, backups

    def _assert_js_syntax(self, path: Path, source: str) -> None:
        import subprocess
        import tempfile

        node = find_cursor_agent_bundle()
        node_exe = (node / "node.exe") if node and (node / "node.exe").exists() else Path("node")
        with tempfile.NamedTemporaryFile(
            "w", suffix=".js", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(source)
            tmp_path = tmp.name
        try:
            proc = subprocess.run(
                [str(node_exe), "--check", tmp_path],
                capture_output=True,
                text=True,
                timeout=60,
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()
            raise RuntimeError(f"JS syntax check failed on {path.name}: {err}")

    def _patch_boot_cmd(self, root: Path, dry_run: bool) -> tuple[bool, Optional[Path], Optional[Path]]:
        cmd = root / "cursor-agent.cmd"
        if not cmd.exists():
            return False, None, None
        text = cmd.read_text(encoding="utf-8", errors="ignore")
        if BOOT_MARKER in text:
            return True, None, None
        # 插在 @echo off / setlocal 之后
        lines = text.splitlines(keepends=True)
        insert_at = 0
        for i, line in enumerate(lines[:8]):
            if line.strip().lower().startswith("@echo") or line.strip().lower().startswith("setlocal"):
                insert_at = i + 1
        boot = _BOOT_BLOCK if _BOOT_BLOCK.endswith("\n") else _BOOT_BLOCK + "\n"
        new_text = "".join(lines[:insert_at]) + "\n" + boot + "".join(lines[insert_at:])
        if dry_run:
            return True, None, None
        bak = cmd.with_suffix(cmd.suffix + f".bak.{time.strftime('%Y%m%d%H%M%S')}")
        bak.write_text(text, encoding="utf-8")
        cmd.write_text(new_text, encoding="utf-8")
        logger.info("Patched auto-boot into {}", cmd)
        return True, cmd, bak

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
        hot_hits, _, _ = self._patch_hot_auth(index, dry_run=True)
        root = find_cursor_agent_root()

        if dry_run:
            return PatchResult(
                status=PatchStatus.APPLIED if hot_hits >= 1 or MARKER in content else PatchStatus.FAILED,
                message=f"[dry-run] hot-auth hits={hot_hits}, would install sc/auto-boot at {root}",
                patch_name=self.metadata.name,
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        if hot_hits == 0 and MARKER not in content:
            return PatchResult(
                status=PatchStatus.FAILED,
                message="未匹配到 AuthStorage 缓存片段（cursor-agent 版本可能已变）",
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

        stripped, slash_files, slash_baks = self._strip_slash(target, dry_run=False)
        files.extend(slash_files)
        backups.extend(slash_baks)

        cfg_copied = ensure_sc_config_from_client(force=True)
        if cfg_copied:
            files.append(cfg_copied)

        if root is not None:
            src = get_project_root() / "src"
            cmd = root / "sc.cmd"
            ps1 = root / "sc.ps1"
            sl_cmd = root / "sc-statusline.cmd"
            cmd.write_text(_SC_CMD, encoding="utf-8")
            ps1.write_text(_sc_ps1(src), encoding="utf-8")
            sl_cmd.write_text(_SC_STATUSLINE_CMD, encoding="utf-8")
            files.extend([cmd, ps1, sl_cmd])
            boot_ok, boot_file, boot_bak = self._patch_boot_cmd(root, dry_run=False)
            if boot_file:
                files.append(boot_file)
            if boot_bak:
                backups.append(boot_bak)
            cfg_path = merge_status_line(str(sl_cmd.resolve()))
            files.append(cfg_path)
            logger.info("Wired statusLine → {}", cfg_path)
        else:
            boot_ok = False

        return PatchResult(
            status=PatchStatus.APPLIED,
            message=(
                f"hot-auth + auto-boot + statusline 已应用 "
                f"(hot={hot_hits}, slash_removed={stripped}, boot={boot_ok}, "
                f"config={cfg_copied}, root={root})"
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
                message="[dry-run] would rollback hot-auth, boot, slash, sc launchers",
                patch_name=self.metadata.name,
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        if restored != content:
            index.write_text(restored, encoding="utf-8")
            files.append(index)
        _, slash_files, _ = self._strip_slash(target, dry_run=False)
        files.extend(slash_files)
        root = find_cursor_agent_root()
        if root:
            cmd = root / "cursor-agent.cmd"
            if cmd.exists():
                text = cmd.read_text(encoding="utf-8", errors="ignore")
                if BOOT_MARKER in text:
                    # 去掉 boot 块：从 marker 到下一空行/原内容
                    lines = text.splitlines(keepends=True)
                    out: list[str] = []
                    skip = False
                    for line in lines:
                        if BOOT_MARKER in line:
                            skip = True
                            continue
                        if skip:
                            if line.strip() == "" and out and not out[-1].strip().startswith("REM"):
                                skip = False
                            if skip and (
                                line.strip().startswith("REM ")
                                or line.strip().startswith("if exist")
                                or line.strip().startswith("start ")
                                or line.strip() == ")"
                                or line.strip() == ""
                            ):
                                if line.strip() == ")" or (
                                    line.strip() == "" and "start" in "".join(out[-5:])
                                ):
                                    if line.strip() == ")":
                                        skip = False
                                    continue
                                continue
                            skip = False
                        out.append(line)
                    cmd.write_text("".join(out), encoding="utf-8")
                    files.append(cmd)
            for name in ("sc.cmd", "sc.ps1", "sc-statusline.cmd"):
                p = root / name
                if p.exists():
                    p.unlink()
                    files.append(p)
        return PatchResult(
            status=PatchStatus.NOT_APPLIED,
            message="已回滚 hot-auth、auto-boot、slash，并移除 sc 启动器",
            patch_name=self.metadata.name,
            files_modified=files,
            duration_ms=int((time.monotonic() - start) * 1000),
        )
