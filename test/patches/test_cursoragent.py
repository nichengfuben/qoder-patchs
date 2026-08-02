"""cursor-agent 补丁单元测试：hot-auth 替换、UI 片段、元数据。"""

from __future__ import annotations

from pathlib import Path

import pytest

from patches.cursor.cursor_agent import (
    BOOT_MARKER,
    DISK_MARKER,
    EPHEMERAL_NULL_MARKER,
    FOOTER_KEEP_MARKER,
    MARKER,
    SLASH_MARKER,
    STATUS_INTERVAL_MARKER,
    _COMPILE_CACHE_NEW,
    _COMPILE_CACHE_OLD,
    _DISK_BEARER_OVERRIDE,
    _GET_ACCESS_NOCACHE,
    CursorAgentPatch,
    apply_hot_auth_replacements,
    find_client_config,
)
from patches.cursor.cursor_hotauth import _ACTION_REQUIRED_NEW
from patches.cursor.cursor_chunks import (
    _FOOTER_KEEP_NEW,
    _FOOTER_KEEP_OLD,
    _SLASH_ANCHOR,
    _SLASH_INJECT,
    _STATUS_INTERVAL_NEW,
    _STATUS_INTERVAL_OLD,
    apply_statusline_interval_text,
)

from test.patches.cursoragent.helpers import (
    FIXTURE_DIR,
    INDEX_GZ,
    UICHUNK_GZ,
    virgin_replacements,
)

_VIRGIN_CACHE_SHORT = "if(this.cachedAccessToken)return this.cachedAccessToken"
_VIRGIN_EPHEMERAL_R = "ephemeralToken:R,isTokenExpiringSoon:Q,"
_VIRGIN_EPHEMERAL_I = "return yield(0,r.Zn)({currentToken:l,ephemeralToken:i,isTokenExpiringSoon:a,"
_VIRGIN_FACTORY = (
    'function A(e){var t;const n=null!==(t=e.store)&&void 0!==t?t:"default";'
    'return"memory"===n?new m:"file"===n?new a(e.domain):'
    '"darwin"===(0,r.platform)()?new u(e.domain):new a(e.domain)}'
)


def test_fixture_files_exist() -> None:
    assert INDEX_GZ.is_file()
    assert UICHUNK_GZ.is_file()
    assert (FIXTURE_DIR / "VERSION.txt").is_file()


def test_virgin_index_contains_all_hot_auth_sources(virgin_index: str) -> None:
    missing = [old[:72] for old, _ in virgin_replacements() if old not in virgin_index]
    assert missing == [], f"virgin index 缺少 {len(missing)} 条原串: {missing[:3]}"


def test_hot_auth_on_virgin_index_matches_expectations(virgin_index: str) -> None:
    out, hits = apply_hot_auth_replacements(virgin_index)
    assert hits >= len(virgin_replacements())
    assert MARKER in out
    assert EPHEMERAL_NULL_MARKER in out
    assert DISK_MARKER in out
    assert _DISK_BEARER_OVERRIDE in out
    assert _GET_ACCESS_NOCACHE in out
    assert "function A(e){/*agentcli-hot-auth*/return new a(e.domain)}" in out
    assert "function l(e){/*agentcli-hot-auth*/i=null}" in out
    assert "function c(e){/*agentcli-hot-auth*/o=null}" in out
    assert "/*agentcli-hot-auth*/if(t&&!r(t))return t" in out
    assert "r(null),yield n()" in out
    assert _VIRGIN_CACHE_SHORT not in out
    assert _VIRGIN_EPHEMERAL_R not in out
    assert _VIRGIN_EPHEMERAL_I not in out
    assert _VIRGIN_FACTORY not in out
    assert "ephemeralToken:R," not in out
    assert "setEphemeralToken:e=>{R=e}" not in out
    assert "this.cachedAccessToken=t.accessToken" not in out
    assert "agentcli-hot-auth-wait" in out
    assert "agentcli-hot-auth-resume" in out
    assert "__agentcliRunSub=_sub" in out
    assert "function _agentcliWaitAuthUpgrade(t)" in out
    assert "_agentcliWaitAuthUpgrade(t);" in out
    assert "agentcli-need-switch.json" in out
    assert "__agentcliFailTok=_failTok" in out
    assert "_tok!==_failTok" in out
    assert "__agentcliAuthSwitched=1" in out
    assert 'if(C){_agentcliWaitAuthUpgrade({action:"upgrade"})' in out
    assert _ACTION_REQUIRED_NEW in out
    assert "/usage limit|free requests/i.test(_ti)" in out


def test_hot_auth_idempotent_on_virgin(virgin_index: str) -> None:
    once, hits1 = apply_hot_auth_replacements(virgin_index)
    twice, hits2 = apply_hot_auth_replacements(once)
    assert once == twice
    assert hits2 >= hits1


def test_each_virgin_old_becomes_new(virgin_index: str) -> None:
    for old, new in virgin_replacements():
        assert old in virgin_index
        patched, hits = apply_hot_auth_replacements(old)
        assert hits >= 1
        assert new in patched
        assert old not in patched


def test_uichunk_status_footer_slash_on_virgin(virgin_uichunk: str) -> None:
    text = virgin_uichunk
    assert _STATUS_INTERVAL_OLD in text and STATUS_INTERVAL_MARKER not in text
    status, label = apply_statusline_interval_text(text)
    assert label == "patch"
    needles = (
        STATUS_INTERVAL_MARKER,
        "setInterval(r,w)",
        "_scPl.current",
        "S(_scPl.current,n.signal)",
        "}),[b,w,S,x]",
    )
    assert all(n in status for n in needles)
    assert _STATUS_INTERVAL_OLD not in status
    assert "setInterval((()=>C(E.payload)),w)" not in status
    assert "}),[E,C,b,w,S]" not in status
    assert _FOOTER_KEEP_OLD in status and FOOTER_KEEP_MARKER not in status
    footer = status.replace(_FOOTER_KEEP_OLD, _FOOTER_KEEP_NEW, 1)
    assert FOOTER_KEEP_MARKER in footer
    assert _FOOTER_KEEP_OLD not in footer

    assert _SLASH_ANCHOR in footer and SLASH_MARKER not in footer
    slash = footer.replace(_SLASH_ANCHOR, _SLASH_INJECT, 1)
    assert SLASH_MARKER in slash
    assert 'ue.push({id:"sc"' in slash
    assert _SLASH_ANCHOR in slash


def test_compile_cache_ps1_snippet() -> None:
    assert "NODE_COMPILE_CACHE" in _COMPILE_CACHE_OLD
    assert "Remove-Item Env:NODE_COMPILE_CACHE" in _COMPILE_CACHE_NEW


def test_metadata_and_markers() -> None:
    patch = CursorAgentPatch()
    assert patch.metadata.name == "cursor-agent"
    assert patch.metadata.version == "2.4.0"
    assert MARKER == "/*agentcli-hot-auth*/"
    assert DISK_MARKER == "/*agentcli-hot-auth-disk*/"
    assert BOOT_MARKER == "REM agentcli-sc-auto-boot"
    assert STATUS_INTERVAL_MARKER == "/*agentcli-status-interval*/"
    assert FOOTER_KEEP_MARKER == "/*agentcli-footer-keep*/"
    assert SLASH_MARKER == "/*agentcli-sc-slash*/"


def test_find_client_config_requires_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("AGENTCLI_SC_CONFIG_SRC", raising=False)
    monkeypatch.delenv("PATCHER_CONFIG", raising=False)
    monkeypatch.delenv("PATCHER_SC_CONFIG_SRC", raising=False)
    assert find_client_config() is None
    src = tmp_path / "config.json"
    src.write_text('{"base_url":"","api_keys":[]}', encoding="utf-8")
    monkeypatch.setenv("PATCHER_CONFIG", str(src))
    path = find_client_config()
    assert path is not None
    assert path.name == "config.json"
