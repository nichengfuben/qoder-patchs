from __future__ import annotations

"""换号成功后通知 Agent UI 自动提交「继续」。"""

import json
import time
from pathlib import Path

from sc.core.paths import sc_home_dir


def nudge_json_path() -> Path:
    return sc_home_dir() / "sc_nudge.json"


def request_continue_nudge(text: str = "继续") -> Path:
    """写入一次性 nudge；Agent 侧轮询到后 submitMessage 并删除文件。"""
    path = nudge_json_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "action": "continue",
        "text": text or "继续",
        "ts": int(time.time() * 1000),
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    return path
