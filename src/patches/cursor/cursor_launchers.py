from __future__ import annotations

"""Cursor Agent launcher scripts and SC wiring (Windows + Unix)."""

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
$sl = Join-Path $root "sc-statusline.cmd"
if (Test-Path -LiteralPath $sl) {
  Start-Process -FilePath "cmd.exe" -ArgumentList @("/c", "echo {}| `"$sl`"") -WindowStyle Hidden -NoNewWindow | Out-Null
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

_UNIX_WRAPPER_MARKER = "# agentcli-sc-auto-boot"


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
        'if exist "%PYTHONPATH%\\sc\\statusline_fast.py" (\n'
        '  "%PY%" -S -X utf8 "%PYTHONPATH%\\sc\\statusline_fast.py"\n'
        ") else (\n"
        '  "%PY%" -X utf8 -m sc.statusline_fast\n'
        ")\n"
    )


def _bash_py_env(src_dir: Path) -> str:
    src = str(src_dir).replace("'", "'\"'\"'")
    return f"""export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
if [ -n "${{PATCHER_SRC:-}}" ]; then export PYTHONPATH="$PATCHER_SRC"
elif [ -n "${{AGENTCLI_PATCHS_SRC:-}}" ]; then export PYTHONPATH="$AGENTCLI_PATCHS_SRC"
else export PYTHONPATH='{src}'
fi
if [ -n "${{PATCHER_PYTHON:-}}" ]; then PY="$PATCHER_PYTHON"
elif [ -n "${{AGENTCLI_PYTHON:-}}" ]; then PY="$AGENTCLI_PYTHON"
else PY=python3
fi
command -v "$PY" >/dev/null 2>&1 || PY=python
"""


def sc_sh(src_dir: Path) -> str:
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        + _bash_py_env(src_dir)
        + 'exec "$PY" -X utf8 -m sc "$@"\n'
    )


def sc_statusline_sh(src_dir: Path) -> str:
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        + _bash_py_env(src_dir)
        + 'if [ -f "$PYTHONPATH/sc/statusline_fast.py" ]; then exec "$PY" -S -X utf8 "$PYTHONPATH/sc/statusline_fast.py"; fi\n'
        + 'exec "$PY" -X utf8 -m sc.statusline_fast\n'
    )


def sc_autoboot_sh() -> str:
    return r"""#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
SC="$ROOT/sc"
[ -x "$SC" ] || exit 0
INST="${HOME}/.cursor/sc_instances.json"
if [ -f "$INST" ]; then
  HB="$(python3 -c "
import json,time
from pathlib import Path
p=Path.home()/'.cursor'/'sc_instances.json'
try:
 d=json.loads(p.read_text(encoding='utf-8'))
 lid=d.get('leader_id')
 info=(d.get('instances') or {}).get(lid) or {}
 hb=float(info.get('heartbeat_at') or 0)
 print(hb)
except Exception:
 print(0)
" 2>/dev/null || true)"
  NOW="$(date +%s)"
  if [ -n "$HB" ] && [ "$HB" != "0" ]; then
    AGE=$((NOW - ${HB%.*}))
    if [ "$AGE" -lt 10 ]; then exit 0; fi
  fi
fi
SL="$ROOT/sc-statusline"
[ -x "$SL" ] && printf '{}\n' | "$SL" >/dev/null 2>&1 || true
nohup "$SC" auto --fg >/dev/null 2>&1 &
"""


def unix_agent_wrapper() -> str:
    """versions/<ver>/cursor-agent shell：boot sc auto 后 exec cursor-agent.bin。"""
    return f"""#!/usr/bin/env bash
{_UNIX_WRAPPER_MARKER}
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$DIR/../.." && pwd)"
unset NODE_COMPILE_CACHE || true
if [ -x "$ROOT/sc-autoboot.sh" ]; then
  "$ROOT/sc-autoboot.sh" || true
fi
REAL="$DIR/cursor-agent.bin"
if [ -x "$REAL" ]; then
  exec "$REAL" "$@"
fi
if [ -x "$DIR/node" ] && [ -f "$DIR/index.js" ]; then
  exec "$DIR/node" "$DIR/index.js" "$@"
fi
echo "cursor-agent: missing cursor-agent.bin or node" >&2
exit 1
"""


def install_win_launchers(root: Path, src: Path) -> list[Path]:
    paths = [
        (root / "sc.cmd", _SC_CMD, True),
        (root / "sc.ps1", sc_ps1(src), True),
        (root / "sc-statusline.cmd", sc_statusline_cmd(src), True),
        (root / "sc-autoboot.ps1", _SC_AUTOBOOT_PS1, True),
    ]
    out: list[Path] = []
    for path, text, crlf in paths:
        write_script(path, text, crlf=crlf)
        out.append(path)
    return out


def install_unix_launchers(root: Path, src: Path) -> list[Path]:
    paths = [
        (root / "sc", sc_sh(src)),
        (root / "sc-statusline", sc_statusline_sh(src)),
        (root / "sc-autoboot.sh", sc_autoboot_sh()),
    ]
    out: list[Path] = []
    for path, text in paths:
        write_script(path, text, crlf=False)
        chmod_exec(path)
        out.append(path)
    return out


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


def write_script(path: Path, text: str, *, crlf: bool = False) -> None:
    """无 BOM 写入；Windows 启动器用 CRLF，Unix shell 用 LF。"""
    body = text.replace("\r\n", "\n")
    if crlf:
        body = body.replace("\n", "\r\n")
    path.write_bytes(body.encode("utf-8"))


def chmod_exec(path: Path) -> None:
    try:
        path.chmod(path.stat().st_mode | 0o111)
    except OSError:
        pass


def patch_unix_wrapper(
    bundle: Path, dry_run: bool
) -> tuple[bool, list[Path], list[Path]]:
    """versions/<ver>/cursor-agent → shell 包装；真身 → cursor-agent.bin。"""
    agent = bundle / "cursor-agent"
    real = bundle / "cursor-agent.bin"
    files: list[Path] = []
    backups: list[Path] = []
    if not agent.exists() and not real.exists():
        return False, files, backups
    wanted = unix_agent_wrapper()
    if agent.is_file():
        text = agent.read_text(encoding="utf-8", errors="ignore")
        if _UNIX_WRAPPER_MARKER in text and real.is_file():
            if text.replace("\r\n", "\n") == wanted.replace("\r\n", "\n"):
                return True, files, backups
            if dry_run:
                return True, files, backups
            write_script(agent, wanted, crlf=False)
            chmod_exec(agent)
            files.append(agent)
            return True, files, backups
    if dry_run:
        return True, files, backups
    return _install_unix_wrapper(agent, real, wanted, files, backups)


def _install_unix_wrapper(
    agent: Path, real: Path, wanted: str, files: list[Path], backups: list[Path]
) -> tuple[bool, list[Path], list[Path]]:
    if agent.is_file() and _UNIX_WRAPPER_MARKER not in agent.read_text(
        encoding="utf-8", errors="ignore"
    ):
        if real.exists():
            real.unlink()
        agent.replace(real)
        backups.append(real)
    write_script(agent, wanted, crlf=False)
    chmod_exec(agent)
    if real.exists():
        chmod_exec(real)
        files.append(real)
    files.append(agent)
    logger.info("Installed Unix cursor-agent wrapper → {}", agent)
    return True, files, backups


def rollback_unix_wrapper(bundle: Path) -> list[Path]:
    agent = bundle / "cursor-agent"
    real = bundle / "cursor-agent.bin"
    files: list[Path] = []
    if not real.is_file():
        return files
    if agent.is_file():
        text = agent.read_text(encoding="utf-8", errors="ignore")
        if _UNIX_WRAPPER_MARKER in text:
            agent.unlink()
            files.append(agent)
    if not agent.exists():
        real.replace(agent)
        files.append(agent)
    return files


def rollback_boot_lines(text: str) -> str:
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    skip = False
    for line in lines:
        if BOOT_MARKER in line:
            skip = True
            continue
        if skip:
            if _should_end_boot_skip(line, out):
                skip = False
                continue
            if _is_boot_skip_line(line):
                continue
            skip = False
        out.append(line)
    return "".join(out)


def _is_boot_skip_line(line: str) -> bool:
    s = line.strip()
    return s.startswith(("REM ", "if exist", "start ")) or s in ("", ")")


def _should_end_boot_skip(line: str, out: list[str]) -> bool:
    s = line.strip()
    if s == ")":
        return True
    return s == "" and "start" in "".join(out[-5:])
