from __future__ import annotations

"""Star Cursor HTTP + Cursor usage-summary。"""

import base64
import json
import ssl
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

USAGE_URL = "https://cursor.com/api/usage-summary"


class ApiError(Exception):
    """对齐 Common/client.py：带 status + JSON payload 的 HTTP 错误。"""

    def __init__(self, status: int, payload: Dict[str, Any]):
        self.status = status
        self.payload = payload or {}
        super().__init__(f"HTTP {status}: {payload}")


# 对齐 Common/client.py：浏览器头；本地 7890 等代理对 cursor.com 常 SSL EOF，用量走直连。
_USAGE_HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://cursor.com/agents",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}


def _jwt_payload(token: str) -> Dict[str, Any]:
    try:
        part = token.split(".")[1]
        pad = 4 - len(part) % 4
        if pad != 4:
            part += "=" * pad
        return json.loads(base64.urlsafe_b64decode(part))
    except Exception:
        return {}


def extract_user_id(access_token: str) -> str:
    sub = _jwt_payload(access_token).get("sub", "")
    if not sub:
        return ""
    return sub.split("|", 1)[1] if "|" in sub else sub


def session_cookie(access_token: str) -> str:
    uid = extract_user_id(access_token)
    if not uid:
        return ""
    return f"{uid}%3A%3A{access_token}"


def is_transient_net_error(exc: BaseException) -> bool:
    """SSL 断连 / 超时 / 临时网络错误，可重试。"""
    if isinstance(exc, (TimeoutError, ConnectionError, ssl.SSLError)):
        return True
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, (TimeoutError, ConnectionError, ssl.SSLError, OSError)):
            return True
        text = str(reason or exc).lower()
        return any(
            k in text
            for k in (
                "ssl",
                "eof",
                "timed out",
                "timeout",
                "temporarily",
                "connection reset",
                "connection aborted",
                "broken pipe",
                "unreachable",
                "name resolution",
                "getaddrinfo",
            )
        )
    text = str(exc).lower()
    return "ssl" in text or "unexpected_eof" in text or "timed out" in text


def short_error(exc: BaseException) -> str:
    """statusline / 日志用短错误标签，避免整段 urlopen SSL 原文。"""
    if isinstance(exc, ApiError):
        return f"HTTP{exc.status}"
    text = str(exc)
    low = text.lower()
    if "unexpected_eof" in low or "eof occurred" in low:
        return "SSL断连"
    if "timed out" in low or "timeout" in low:
        return "超时"
    if "ssl" in low:
        return "SSL失败"
    if "getaddrinfo" in low or "name resolution" in low:
        return "DNS失败"
    if "connection reset" in low or "connection aborted" in low:
        return "连接重置"
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP{exc.code}"
    if text.startswith("HTTP "):
        return text.split(":", 1)[0][:12]
    one = text.replace("\n", " ").strip()
    if one.startswith("<urlopen error") or "urlopen error" in low:
        return "网络错误"
    return one[:24] + ("…" if len(one) > 24 else "")


def _build_opener(*, direct: bool) -> urllib.request.OpenerDirector:
    """direct=True 时忽略 HTTP(S)_PROXY，避免本机坏代理打断 cursor.com TLS。"""
    handlers: list = []
    if direct:
        handlers.append(urllib.request.ProxyHandler({}))
    handlers.append(urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    return urllib.request.build_opener(*handlers)


def _http_json(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    body: Optional[Dict[str, Any]] = None,
    timeout: float = 20,
    retries: int = 3,
    direct: bool = False,
) -> Dict[str, Any]:
    data = None
    hdrs = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    opener = _build_opener(direct=direct)
    last: Optional[BaseException] = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            with opener.open(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            payload: Dict[str, Any]
            try:
                payload = json.loads(detail) if detail else {}
                if not isinstance(payload, dict):
                    payload = {"error": detail[:200]}
            except Exception:
                payload = {"error": detail[:200]}
            raise ApiError(exc.code, payload) from exc
        except (urllib.error.URLError, TimeoutError, ssl.SSLError, OSError) as exc:
            last = exc
            if attempt >= retries or not is_transient_net_error(exc):
                raise RuntimeError(short_error(exc)) from exc
            time.sleep(min(0.8 * attempt, 2.0))
    raise RuntimeError(short_error(last or RuntimeError("网络错误")))


def pull_token(base_url: str, api_key: str, *, timeout: float = 20) -> Dict[str, Any]:
    """对齐 Common/client.py：``GET /api/v1/pull-token`` + ``X-API-Key``。"""
    url = base_url.rstrip("/") + "/api/v1/pull-token"
    return _http_json(
        "GET",
        url,
        headers={"X-API-Key": api_key},
        timeout=timeout,
        retries=1,
    )


def key_status(base_url: str, api_key: str, *, timeout: float = 20) -> Dict[str, Any]:
    """对齐 Common/client.py：``GET /api/v1/key-status``。"""
    url = base_url.rstrip("/") + "/api/v1/key-status"
    return _http_json(
        "GET",
        url,
        headers={"X-API-Key": api_key},
        timeout=timeout,
        retries=2,
    )


def fetch_usage(access_token: str, *, timeout: float = 20) -> Dict[str, Any]:
    """查 cursor.com 用量：直连 + 浏览器头；单次请求，失败由调用方忽略上次快照。"""
    cookie = session_cookie(access_token)
    hdrs = dict(_USAGE_HEADERS)
    hdrs["Cookie"] = f"WorkosCursorSessionToken={cookie}"
    return _http_json(
        "GET",
        USAGE_URL,
        headers=hdrs,
        timeout=timeout,
        retries=1,
        direct=True,
    )


def extract_tokens(data: Dict[str, Any]) -> Tuple[str, str, str, str]:
    """对齐 Common/client.py ``extract_tokens_from_pull``。"""
    ct = data.get("cursor_token") or {}
    if isinstance(ct, str) and ct:
        return ct, ct, "", str(data.get("card_number") or data.get("card") or "")
    if not isinstance(ct, dict):
        ct = {}
    access = str(
        ct.get("access_token")
        or ct.get("accessToken")
        or data.get("access_token")
        or data.get("accessToken")
        or ""
    )
    refresh = str(
        ct.get("refresh_token")
        or ct.get("refreshToken")
        or data.get("refresh_token")
        or data.get("refreshToken")
        or access
    )
    email = str(ct.get("email") or data.get("email") or "")
    card = str(data.get("card_number") or data.get("card") or data.get("card_type") or "")
    return access, refresh, email, card


def _usage_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except Exception:
        return default


def _usage_status(total_pct: float, is_unlimited: bool) -> str:
    if is_unlimited:
        return "UNLIMITED"
    if total_pct >= 100:
        return "LIMIT"
    if total_pct >= 95:
        return "NEAR_LIMIT"
    return "OK"


def parse_usage(data: Dict[str, Any]) -> Dict[str, Any]:
    """对齐 Common/client.py ``parse_usage``：总用量 = (auto + api) / 2。"""
    plan = (
        data.get("individualUsage", {}).get("plan", {})
        if isinstance(data, dict)
        else {}
    )
    breakdown = plan.get("breakdown") or {}
    total = _usage_float(breakdown.get("total"))
    included = _usage_float(breakdown.get("included"))
    bonus = _usage_float(breakdown.get("bonus"))
    auto_pct = _usage_float(plan.get("autoPercentUsed"))
    api_pct = _usage_float(plan.get("apiPercentUsed"))
    # 总用量唯一算法：(auto + api) / 2；不用 API 的 totalPercentUsed
    total_pct = (auto_pct + api_pct) / 2.0
    used = round(total * total_pct / 100.0, 2) if total > 0 else 0.0
    remaining = max(total - used, 0.0)
    membership = str(data.get("membershipType") or "-")
    is_unlimited = bool(data.get("isUnlimited", False))
    msg = str(
        data.get("autoModelSelectedDisplayMessage")
        or data.get("namedModelSelectedDisplayMessage")
        or ""
    )
    status = _usage_status(total_pct, is_unlimited)
    return {
        "total": total,
        "used": used,
        "remaining": remaining,
        "included": included,
        "bonus": bonus,
        "total_pct": total_pct,
        "auto_pct": auto_pct,
        "api_pct": api_pct,
        "status": status,
        "membership": membership,
        "is_unlimited": is_unlimited,
        "message": msg,
        "billing_end": str(data.get("billingCycleEnd") or ""),
    }


def is_limit_reached(usage: Dict[str, Any], threshold: float) -> bool:
    if usage.get("is_unlimited"):
        return False
    total = float(usage.get("total_pct") or 0)
    auto = float(usage.get("auto_pct") or 0)
    api = float(usage.get("api_pct") or 0)
    # Cursor 服务端按 auto/api 单项拒 Agent；total=(auto+api)/2 会严重滞后
    if total >= threshold or auto >= threshold or api >= threshold:
        return True
    membership = str(usage.get("membership") or "").lower()
    if membership == "free" and auto >= 50.0:
        return True
    return False
