"""UTF-8 stdio helper."""

from __future__ import annotations

import os

from sc.encoding import ensure_utf8_stdio, utf8_env


def test_ensure_utf8_sets_env(monkeypatch) -> None:
    monkeypatch.delenv("PYTHONUTF8", raising=False)
    monkeypatch.delenv("PYTHONIOENCODING", raising=False)
    ensure_utf8_stdio()
    assert os.environ.get("PYTHONUTF8") == "1"
    assert os.environ.get("PYTHONIOENCODING") == "utf-8"


def test_utf8_env_merges() -> None:
    env = utf8_env({"FOO": "1"})
    assert env["FOO"] == "1"
    assert env["PYTHONUTF8"] == "1"
