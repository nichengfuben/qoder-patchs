from __future__ import annotations

"""Star Cursor HTTP + Cursor usage-summary。"""

import base64
import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

USAGE_URL = "https://cursor.com/api/usage-summary"


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


def _http_json(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    body: Optional[Dict[str, Any]] = None,
    timeout: float = 20,
) -> Dict[str, Any]:
    data = None
    hdrs = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail[:200]}") from exc


def pull_token(base_url: str, api_key: str, *, timeout: float = 20) -> Dict[str, Any]:
    url = base_url.rstrip("/") + "/api/pull-token"
    return _http_json(
        "POST", url,
        headers={"Authorization": f"Bearer {api_key}"},
        body={}, timeout=timeout,
    )


def fetch_usage(access_token: str, *, timeout: float = 20) -> Dict[str, Any]:
    cookie = session_cookie(access_token)
    return _http_json(
        "GET", USAGE_URL,
        headers={"Cookie": f"WorkosCursorSessionToken={cookie}"},
        timeout=timeout,
    )


def extract_tokens(data: Dict[str, Any]) -> Tuple[str, str, str, str]:
    access = str(data.get("access_token") or data.get("accessToken") or "")
    refresh = str(data.get("refresh_token") or data.get("refreshToken") or access)
    email = str(data.get("email") or "")
    card = str(data.get("card") or data.get("card_type") or "")
    return access, refresh, email, card


def parse_usage(data: Dict[str, Any]) -> Dict[str, Any]:
    plan = (data.get("individualUsage") or {}).get("plan") or {}
    breakdown = plan.get("breakdown") or {}

    def f(v: Any) -> float:
        try:
            return float(v) if v is not None else 0.0
        except Exception:
            return 0.0

    return {
        "total_pct": f(plan.get("totalPercentUsed")),
        "auto_pct": f(plan.get("autoPercentUsed")),
        "api_pct": f(plan.get("apiPercentUsed")),
        "included": f(breakdown.get("included")),
        "bonus": f(breakdown.get("bonus")),
        "total": f(breakdown.get("total")),
    }


def is_limit_reached(usage: Dict[str, Any], threshold: float) -> bool:
    return float(usage.get("total_pct") or 0) >= float(threshold)
