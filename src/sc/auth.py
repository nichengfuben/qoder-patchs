from __future__ import annotations

"""读写 cursor-agent 同源 auth.json。"""

import json
import os
import time
import uuid
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
    """写入 auth.json；整文件重写以触发 Agent 热读（mtime 变化）。

    根因说明（曾出现「写入失败」）：
    - 旧实现用固定临时名 ``auth.tmp``（``Path.with_suffix('.tmp')``）。
    - ``sc auto`` leader 与手动 ``sc pull`` 并发时会抢同一个 tmp，
      ``Path.replace`` 在 Windows 上抛 ``PermissionError`` / ``WinError 32``，
      异常被裸 ``except`` 吞掉，只返回 False。
    - 修复：每进程唯一 tmp + 有限次重试 + 失败时打印真实异常。
    """
    path = auth_json_path()
    last_exc: Optional[BaseException] = None
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
        data.pop("access_token", None)
        data.pop("refresh_token", None)
        text = json.dumps(data, ensure_ascii=False, indent=2)
    except Exception as exc:
        print(f"write_auth 准备失败: {type(exc).__name__}: {exc}")
        return False

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
            # 目的文件被 Cursor/agent 短暂占用时退避重试
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
