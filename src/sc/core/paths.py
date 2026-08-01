from __future__ import annotations

"""Cursor Agent auth 路径与 SC 数据目录（~/.cursor）。"""

import os
import platform
import shutil
from pathlib import Path
from typing import Optional


def sc_home_dir() -> Path:
    """SC 配置与运行时状态：``~/.cursor``（与 cli-config / instances 同目录）。"""
    return Path.home() / ".cursor"


def cursor_auth_dir() -> Path:
    """cursor-agent ``auth.json`` 目录（与 JS hot-auth 对齐）。"""
    if platform.system() == "Windows":
        appdata = os.environ.get("APPDATA") or str(
            Path.home() / "AppData" / "Roaming"
        )
        return Path(appdata) / "Cursor"
    # Linux / macOS：JS 非 win32 一律 ~/.cursor
    return Path.home() / ".cursor"


def cursor_config_dir() -> Path:
    """兼容旧名：等同 ``cursor_auth_dir``（仅 auth / bearer）。"""
    return cursor_auth_dir()


def auth_json_path() -> Path:
    return cursor_auth_dir() / "auth.json"


def config_json_path() -> Path:
    """SC ``config.json``：始终在 ``~/.cursor``。"""
    return sc_home_dir() / "config.json"


_LEGACY_SC_NAMES = (
    "config.json",
    "sc_status.json",
    "sc_auto.pid",
    "sc_auto.log",
)


def migrate_legacy_sc_home() -> None:
    """若 ``~/.cursor`` 缺文件而 auth 目录仍有旧 SC 文件，则复制过去（不删源）。"""
    home = sc_home_dir()
    home.mkdir(parents=True, exist_ok=True)
    legacy = cursor_auth_dir()
    if legacy.resolve() == home.resolve():
        return
    for name in _LEGACY_SC_NAMES:
        dst = home / name
        src = legacy / name
        if dst.exists() or not src.is_file():
            continue
        try:
            shutil.copy2(src, dst)
        except Exception:
            pass


def _windows_agent_root() -> Optional[Path]:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        root = Path(local) / "cursor-agent"
        if root.is_dir():
            return root
    home = Path.home() / "AppData" / "Local" / "cursor-agent"
    return home if home.is_dir() else None


def _unix_share_root() -> Path:
    return Path.home() / ".local" / "share" / "cursor-agent"


def _root_from_symlink(link: Path) -> Optional[Path]:
    """``~/.local/bin/agent`` → ``.../versions/<ver>/cursor-agent`` → share root。"""
    try:
        if not link.exists():
            return None
        target = link.resolve()
    except OSError:
        return None
    # .../versions/<ver>/cursor-agent[.bin]
    if target.parent.name and target.parent.parent.name == "versions":
        root = target.parent.parent.parent
        return root if root.is_dir() else None
    if (target / "versions").is_dir():
        return target
    return None


def _unix_agent_root() -> Optional[Path]:
    share = _unix_share_root()
    if share.is_dir():
        return share
    for name in ("cursor-agent", "agent"):
        root = _root_from_symlink(Path.home() / ".local" / "bin" / name)
        if root is not None:
            return root
    return None


def find_cursor_agent_root() -> Optional[Path]:
    """安装根（含 ``versions/``）：Win=%LOCALAPPDATA%/cursor-agent；Unix=~/.local/share/cursor-agent。"""
    if platform.system() == "Windows":
        return _windows_agent_root()
    return _unix_agent_root()


def _version_sort_key(p: Path) -> tuple:
    parts = p.name.split("-")
    date = parts[0] if parts else ""
    return date, p.name


def find_cursor_agent_bundle() -> Optional[Path]:
    """最新 version 目录（含 index.js；Win 可有 node.exe，Unix 可有 node / cursor-agent.bin）。"""
    root = find_cursor_agent_root()
    if root is None:
        return None
    versions = root / "versions"
    if not versions.is_dir():
        if (root / "index.js").exists():
            return root
        return None
    dirs = [p for p in versions.iterdir() if p.is_dir() and (p / "index.js").exists()]
    if not dirs:
        return None
    dirs.sort(key=_version_sort_key, reverse=True)
    return dirs[0]
