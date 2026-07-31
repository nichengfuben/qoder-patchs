from __future__ import annotations

"""Cursor Agent launcher scripts and SC wiring."""

import json
import os
import shutil
from pathlib import Path
from typing import Optional

from loguru import logger

from patches.cursor.cursor_hotauth import BOOT_MARKER
from sc.core.paths import config_json_path

_BOOT_BLOCK = f"""{BOOT_MARKER}
REM Start sc auto via helper script (avoids cmd quoting bugs); parent=cmd.exe
if exist "%~dp0sc-autoboot.ps1" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0sc-autoboot.ps1"
"""

_SC_AUTOBOOT_PS1 = r"""$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$sc = Join-Path $root "sc.cmd"
if (-not (Test-Path -LiteralPath $sc)) { exit 0 }
$inst = Join-Path $env:USERPROFILE ".cursor\sc_instances.json"
if (Test-Path -LiteralPath $inst) {
  try {
    $doc = Get-Content -LiteralPath $inst -Raw -Encoding UTF8 | ConvertFrom-Json
    $lid = $doc.leader_id
    if ($lid) {
      $info = $doc.instances.$lid
      if ($null -ne $info -and $null -ne $info.heartbeat_at) {
        $hb = [double]$info.heartbeat_at
        $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        if (($now - $hb) -lt 10) { exit 0 }
      }
    }
  } catch {}
}
$argv = @("auto", "--fg")
Start-Process -FilePath $sc -ArgumentList $argv -WindowStyle Hidden | Out-Null
"""

_AG_CMD = r"""@echo off
setlocal EnableExtensions
set "CURSOR_INVOKED_AS=%~nx0"
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "_PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
set "_SCRIPT=%SCRIPT_DIR%\cursor-agent.ps1"
REM agentcli-no-terminate-prompt
endlocal & set "CURSOR_INVOKED_AS=%~nx0" & "%_PS%" -NoProfile -ExecutionPolicy Bypass -File "%_SCRIPT%" %*
"""

_CURSOR_AGENT_CMD_TAIL = r"""set "CURSOR_INVOKED_AS=%~nx0"
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "_PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
set "_SCRIPT=%SCRIPT_DIR%\cursor-agent.ps1"
REM agentcli-no-terminate-prompt
endlocal & set "CURSOR_INVOKED_AS=%~nx0" & "%_PS%" -NoProfile -ExecutionPolicy Bypass -File "%_SCRIPT%" %*
"""

_SC_CMD = r"""@echo off
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set "SCRIPT_DIR=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%sc.ps1" %*
"""


def sc_ps1(src_dir: Path) -> str:
    src = str(src_dir).replace("'", "''")
    return f"""param([Parameter(ValueFromRemainingArguments=$true)]$ArgsRest)
$ErrorActionPreference = "Stop"
try {{ chcp 65001 | Out-Null }} catch {{}}
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONPATH = if ($env:PATCHER_SRC) {{ $env:PATCHER_SRC }} elseif ($env:AGENTCLI_PATCHS_SRC) {{ $env:AGENTCLI_PATCHS_SRC }} else {{ '{src}' }}
$py = if ($env:PATCHER_PYTHON) {{ $env:PATCHER_PYTHON }} elseif ($env:AGENTCLI_PYTHON) {{ $env:AGENTCLI_PYTHON }} else {{ 'python' }}
& $py -X utf8 -m sc @ArgsRest
exit $LASTEXITCODE
"""


def sc_statusline_cmd(src_dir: Path) -> str:
    src = str(src_dir).replace("%", "%%")
    return (
        "@echo off\n"
        "setlocal\n"
        "set PYTHONUTF8=1\n"
        "set PYTHONIOENCODING=utf-8\n"
        'if defined PATCHER_SRC (set "PYTHONPATH=%PATCHER_SRC%") else if defined AGENTCLI_PATCHS_SRC (set "PYTHONPATH=%AGENTCLI_PATCHS_SRC%") '
        f'else (set "PYTHONPATH={src}")\n'
        'if defined PATCHER_PYTHON (set "PY=%PATCHER_PYTHON%") else if defined AGENTCLI_PYTHON (set "PY=%AGENTCLI_PYTHON%") else (set "PY=python")\n'
        '"%PY%" -X utf8 -m sc.run.status_store\n'
    )


def find_client_config() -> Optional[Path]:
    env = (
        os.environ.get("PATCHER_CONFIG", "").strip()
        or os.environ.get("AGENTCLI_SC_CONFIG_SRC", "").strip()
    )
    if not env:
        return None
    p = Path(env)
    return p if p.is_file() else None


def ensure_sc_config_from_client(*, force: bool = False) -> Optional[Path]:
    src = find_client_config()
    if src is None:
        return None
    dst = config_json_path()
    if dst.exists() and not force:
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
