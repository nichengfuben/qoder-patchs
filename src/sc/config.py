from __future__ import annotations

"""SC 配置 I/O（config.json 与 auth.json 同级）。

``base_url`` / ``api_keys`` 等仅来自本机 ``config.json``，代码内不写死服务地址或密钥。
"""

import json
from pathlib import Path
from typing import Any, Dict

from sc.paths import config_json_path, cursor_config_dir

# 非敏感运行默认值；base_url / api_keys 必须由用户 config.json 提供
DEFAULT_CONFIG: Dict[str, Any] = {
    "base_url": "",
    "api_keys": [],
    # Key 日用量轮换阈值（client KeyPool.switch_threshold）
    "switch_threshold": 80,
    # Cursor 账号换号阈值（client /auto 只用这个）
    "usage_threshold": 95.0,
    "poll_interval": 5,
    "status_refresh_interval": 5,
    "request_timeout": 20,
    "max_retry_per_pull": 3,
}


def load_config() -> Dict[str, Any]:
    path = config_json_path()
    if not path.exists():
        cfg = dict(DEFAULT_CONFIG)
        save_config(cfg)
        return cfg
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {**DEFAULT_CONFIG, **raw}
    except Exception:
        return dict(DEFAULT_CONFIG)


def save_config(cfg: Dict[str, Any]) -> Path:
    path = config_json_path()
    cursor_config_dir().mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
