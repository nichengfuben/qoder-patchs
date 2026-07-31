"""Tests for sc.auth helpers."""

from __future__ import annotations

import base64
import json

from sc.auth import token_subject


def _fake_jwt(payload: dict) -> str:
    head = base64.urlsafe_b64encode(b'{"alg":"none"}').decode().rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{head}.{body}.sig"


def test_token_subject_reads_sub() -> None:
    tok = _fake_jwt({"sub": "auth0|user_TEST", "exp": 9999999999})
    assert token_subject(tok) == "auth0|user_TEST"


def test_token_subject_invalid() -> None:
    assert token_subject("") is None
    assert token_subject("not-a-jwt") is None
    # None → 回落到盘上 auth.json（本机有 token 时非空）；显式空串才表示无 token
    assert token_subject("a.b") is None
