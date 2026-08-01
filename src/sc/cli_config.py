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
            loaded = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(loaded, dict):
                data = loaded
        except Exception:
            data = {}
    data["statusLine"] = {
        "type": "command",
        "command": command,
        "padding": padding,
        # 1s 读 json 刷新量条/时钟；用量 API 由 sc auto 5s 轮询，不在此命令里打
        "updateIntervalMs": update_ms,
        # Win 冷启动 python 偶发 >2s；超时则 UI 不改字 → 时钟/条看起来“死了”
        "timeoutMs": 5000,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def status_line_command(path: Optional[Path] = None) -> Optional[str]:
    cfg = cli_config_path()
    if not cfg.exists():
        return None
    try:
        data = json.loads(cfg.read_text(encoding="utf-8-sig"))
        sl = data.get("statusLine") or {}
        return str(sl.get("command") or "") or None
    except Exception:
        return None
