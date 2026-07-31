from __future__ import annotations

"""安装 / 合并 Cursor Agent ``cli-config.json`` 的 statusLine。"""

import json
from pathlib import Path
from typing import Any, Dict, Optional


def cli_config_path() -> Path:
    return Path.home() / ".cursor" / "cli-config.json"


def merge_status_line(command: str, *, padding: int = 1, update_ms: int = 1000) -> Path:
    """写入/合并 ``statusLine``，保留用户其它配置。"""
    path = cli_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data: Dict[str, Any] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except Exception:
            data = {}
    data["statusLine"] = {
        "type": "command",
        "command": command,
        "padding": padding,
        "updateIntervalMs": update_ms,
        "timeoutMs": 4000,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def status_line_command(path: Optional[Path] = None) -> Optional[str]:
    cfg = cli_config_path()
    if not cfg.exists():
        return None
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
        sl = data.get("statusLine") or {}
        return str(sl.get("command") or "") or None
    except Exception:
        return None
