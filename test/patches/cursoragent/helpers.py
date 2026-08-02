"""Shared helpers for cursor-agent patch tests."""

from __future__ import annotations

import gzip
import shutil
from pathlib import Path

import pytest

from patches.cursor.cursor_hotauth import _COMPILE_CACHE_OLD
from patches.cursor.cursor_repls import _REPLACEMENTS
from patches.cursor.cursor_chunks import (
    _FOOTER_KEEP_OLD,
    _SLASH_ANCHOR,
    _STATUS_INTERVAL_OLD,
)
from patches.cursor import cursor_patchops as ops

FIXTURE_DIR = Path(__file__).resolve().parent
INDEX_GZ = FIXTURE_DIR / "index.gz"
UICHUNK_GZ = FIXTURE_DIR / "uichunk.gz"

_VIRGIN_CACHE_SHORT = "if(this.cachedAccessToken)return this.cachedAccessToken"


def load_gz(path: Path) -> str:
    assert path.is_file(), f"missing fixture: {path}"
    return gzip.decompress(path.read_bytes()).decode("utf-8")


def load_virgin_index() -> str:
    text = load_gz(INDEX_GZ)
    assert "agentcli-hot-auth" not in text
    assert _VIRGIN_CACHE_SHORT in text
    return text


def load_virgin_uichunk() -> str:
    text = load_gz(UICHUNK_GZ)
    assert "agentcli-" not in text
    assert _STATUS_INTERVAL_OLD in text
    assert _FOOTER_KEEP_OLD in text
    assert _SLASH_ANCHOR in text
    assert 'ue.push({id:"sc"' not in text
    return text


def virgin_replacements() -> list[tuple[str, str]]:
    return [
        (old, new)
        for old, new in _REPLACEMENTS
        if "agentcli-hot-auth" not in old
        and "_agentcli" not in old
        and old != new
    ]


def build_temp_virgin_bundle(
    tmp_path: Path, virgin_index: str, virgin_uichunk: str
) -> tuple[Path, Path, Path, Path]:
    version = tmp_path / "versions" / "2026.07.23-e383d2b"
    version.mkdir(parents=True)
    index = version / "index.js"
    chunk = version / "5305.index.js"
    index.write_text(virgin_index, encoding="utf-8")
    chunk.write_text(virgin_uichunk, encoding="utf-8")
    root = tmp_path
    ps1 = root / "cursor-agent.ps1"
    ps1.write_text(
        "param()\n" + _COMPILE_CACHE_OLD + "\nWrite-Host ok\n",
        encoding="utf-8",
    )
    shutil.copy2(ps1, version / "cursor-agent.ps1")
    (root / "cursor-agent.cmd").write_text(
        "@echo off\r\nnode index.js %*\r\n", encoding="utf-8"
    )
    return root, version, index, chunk


def patch_bundle_paths(
    monkeypatch: pytest.MonkeyPatch, version: Path, root: Path
) -> None:
    monkeypatch.setattr(ops, "find_cursor_agent_bundle", lambda: version)
    monkeypatch.setattr(
        "patches.cursor.cursor_agent.find_cursor_agent_bundle", lambda: version
    )
    monkeypatch.setattr(
        "patches.cursor.cursor_agent.find_cursor_agent_root", lambda: root
    )
    monkeypatch.setattr(
        "sc.core.paths.find_cursor_agent_bundle", lambda: version
    )
    monkeypatch.setattr(
        "sc.core.paths.find_cursor_agent_root", lambda: root
    )
    monkeypatch.setattr(ops, "assert_js_syntax", lambda path, source: None)
