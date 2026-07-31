from __future__ import annotations

"""读写 cursor-agent 同源 auth.json。"""

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from sc.core.paths import auth_json_path, cursor_auth_dir


def read_auth() -> Optional[Dict[str, Any]]:
    path = auth_json_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _build_auth_payload(
    access_token: str, refresh_token: Optional[str] = None
) -> tuple[Optional[str], Path]:
    path = auth_json_path()
    try:
        cursor_auth_dir().mkdir(parents=True, exist_ok=True)
        data: Dict[str, Any] = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        data["accessToken"] = access_token
        data["refreshToken"] = refresh_token or access_token
        data.pop("access_token", None)
        data.pop("refresh_token", None)
        return json.dumps(data, ensure_ascii=False, indent=2), path
    except Exception as exc:
        print(f"write_auth 准备失败: {type(exc).__name__}: {exc}")
        return None, path


def _atomic_write_auth(path: Path, text: str) -> bool:
    last_exc: Optional[BaseException] = None
    for attempt in range(1, 6):
        tmp = path.with_name(f"auth.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
        try:
            tmp.write_text(text, encoding="utf-8")
            os.replace(str(tmp), str(path))
            try:
                os.utime(path, None)
            except Exception:
                pass
            return True
        except Exception as exc:
            last_exc = exc
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
            time.sleep(0.15 * attempt)
            try:
                path.write_text(text, encoding="utf-8")
                try:
                    os.utime(path, None)
                except Exception:
                    pass
                return True
            except Exception as exc2:
                last_exc = exc2
                time.sleep(0.15 * attempt)
    print(
        f"write_auth 失败 path={path} "
        f"err={type(last_exc).__name__ if last_exc else '?'}: {last_exc}"
    )
    return False


def write_auth(access_token: str, refresh_token: Optional[str] = None) -> bool:
    """写入 auth.json；整文件重写以触发 Agent 热读（mtime 变化）。"""
    text, path = _build_auth_payload(access_token, refresh_token)
    if text is None:
        return False
    return _atomic_write_auth(path, text)


def access_token() -> Optional[str]:
    auth = read_auth()
    if not auth:
        return None
    return auth.get("accessToken") or auth.get("access_token")


def token_subject(token: Optional[str] = None) -> Optional[str]:
    """解析 JWT ``sub``（不校验签名；仅用于 status 对照当前号）。"""
    import base64
    import json as _json

    raw = token if token is not None else access_token()
    if not raw or raw.count(".") < 2:
        return None
    try:
        payload = raw.split(".")[1]
        pad = "=" * ((4 - len(payload) % 4) % 4)
        body = _json.loads(base64.urlsafe_b64decode(payload + pad))
        sub = body.get("sub")
        return str(sub) if sub else None
    except Exception:
        return None
