from __future__ import annotations

"""Cursor Agent / IDE auth.json 与同级 config.json 路径。"""

import os
import platform
from pathlib import Path


def cursor_config_dir() -> Path:
    """与 cursor-agent ``getAuthFilePath('Cursor')`` 同级目录。"""
    system = platform.system()
    if system == "Windows":
        appdata = os.environ.get("APPDATA") or str(
            Path.home() / "AppData" / "Roaming"
        )
        return Path(appdata) / "Cursor"
    if system == "Darwin":
        # cursor-agent: join(homedir(), `.${product}`, "auth.json") → ~/.cursor
        return Path.home() / ".cursor"
    xdg = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(xdg) / "cursor"


def auth_json_path() -> Path:
    return cursor_config_dir() / "auth.json"


def config_json_path() -> Path:
    """便携 SC 配置：与 auth.json 同级，不放在执行目录。"""
    return cursor_config_dir() / "config.json"


def find_cursor_agent_root() -> Path | None:
    """``%LOCALAPPDATA%/cursor-agent`` 安装根（含 versions/）。"""
    local = os.environ.get("LOCALAPPDATA")
    if local:
        root = Path(local) / "cursor-agent"
        if root.is_dir():
            return root
    home = Path.home() / "AppData" / "Local" / "cursor-agent"
    return home if home.is_dir() else None


def find_cursor_agent_bundle() -> Path | None:
    """最新 version 目录（含 index.js / node.exe）。"""
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

    def _key(p: Path) -> tuple:
        parts = p.name.split("-")
        date = parts[0] if parts else ""
        return date, p.name

    dirs.sort(key=_key, reverse=True)
    return dirs[0]
