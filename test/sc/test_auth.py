"""Tests for sc.auth helpers and agent path resolution."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from sc.core import paths as P
from sc.core.auth import token_subject


def _fake_jwt(payload: dict) -> str:
    head = base64.urlsafe_b64encode(b'{"alg":"none"}').decode().rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{head}.{body}.sig"


def test_token_subject_reads_sub() -> None:
    tok = _fake_jwt({"sub": "auth0|user_xyz", "exp": 9999999999})
    assert token_subject(tok) == "auth0|user_xyz"


def test_token_subject_invalid() -> None:
    assert token_subject("") is None
    assert token_subject("not-a-jwt") is None
    # 显式空串才表示无 token
    assert token_subject("a.b") is None


def test_auth_dir_windows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(P.platform, "system", lambda: "Windows")
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    assert P.cursor_auth_dir() == tmp_path / "Roaming" / "Cursor"


def test_auth_dir_unix_matches_js(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(P.platform, "system", lambda: "Linux")
    assert P.cursor_auth_dir() == Path.home() / ".cursor"
    monkeypatch.setattr(P.platform, "system", lambda: "Darwin")
    assert P.cursor_auth_dir() == Path.home() / ".cursor"


def test_find_root_windows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "cursor-agent"
    root.mkdir()
    monkeypatch.setattr(P.platform, "system", lambda: "Windows")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert P.find_cursor_agent_root() == root


def test_find_root_unix_share(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    share = tmp_path / ".local" / "share" / "cursor-agent"
    share.mkdir(parents=True)
    monkeypatch.setattr(P.platform, "system", lambda: "Linux")
    monkeypatch.setattr(P, "_unix_share_root", lambda: share)
    assert P.find_cursor_agent_root() == share


def test_root_from_symlink(tmp_path: Path) -> None:
    ver = tmp_path / "share" / "versions" / "2026.07.23-e383d2b"
    ver.mkdir(parents=True)
    agent = ver / "cursor-agent"
    agent.write_text("#!/bin/sh\n", encoding="utf-8")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    link = bindir / "agent"
    try:
        link.symlink_to(agent)
    except OSError:
        pytest.skip("symlink not supported")
    assert P._root_from_symlink(link) == tmp_path / "share"


def test_find_bundle_latest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "cursor-agent"
    older = root / "versions" / "2026.01.01-aaaaaaa"
    newer = root / "versions" / "2026.07.23-e383d2b"
    older.mkdir(parents=True)
    newer.mkdir(parents=True)
    (older / "index.js").write_text("// old", encoding="utf-8")
    (newer / "index.js").write_text("// new", encoding="utf-8")
    monkeypatch.setattr(P, "find_cursor_agent_root", lambda: root)
    assert P.find_cursor_agent_bundle() == newer
