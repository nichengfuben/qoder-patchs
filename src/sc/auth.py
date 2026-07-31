from __future__ import annotations

"""读写 cursor-agent 同源 auth.json。"""

import json
from typing import Any, Dict, Optional

from sc.paths import auth_json_path, cursor_config_dir


def read_auth() -> Optional[Dict[str, Any]]:
    path = auth_json_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_auth(access_token: str, refresh_token: Optional[str] = None) -> bool:
    path = auth_json_path()
    try:
        cursor_config_dir().mkdir(parents=True, exist_ok=True)
        data: Dict[str, Any] = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        data["accessToken"] = access_token
        data["refreshToken"] = refresh_token or access_token
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def access_token() -> Optional[str]:
    auth = read_auth()
    if not auth:
        return None
    return auth.get("accessToken") or auth.get("access_token")
