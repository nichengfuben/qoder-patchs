"""cursor-agent 补丁测试：输入为未打过任何补丁的上游源码 fixture。

Fixture 来源：cursor-agent ``2026.07.23-e383d2b`` 的 virgin 备份
（``index.js.bak.*`` / ``5305.index.js.bak.*``，无 agentcli 标记）。
"""

from __future__ import annotations

import gzip
import shutil
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
    _REPLACEMENTS,
    CursorAgentPatch,
    apply_hot_auth_replacements,
    find_client_config,
)
from patches.cursor.cursor_chunks import (
    _FOOTER_KEEP_NEW,
    _FOOTER_KEEP_OLD,
    _SLASH_ANCHOR,
    _SLASH_INJECT,
    _STATUS_INTERVAL_NEW,
    _STATUS_INTERVAL_OLD,
)
from patches.cursor import cursor_patchops as ops
from core.patch_base import PatchStatus

_FIXTURE_DIR = Path(__file__).resolve().parent / "cursoragent"
_INDEX_GZ = _FIXTURE_DIR / "index.gz"
_UICHUNK_GZ = _FIXTURE_DIR / "uichunk.gz"

# 上游 virgin 原串特征（必须出现在未补丁源码中）
_VIRGIN_CACHE_SHORT = "if(this.cachedAccessToken)return this.cachedAccessToken"
_VIRGIN_EPHEMERAL_R = "ephemeralToken:R,isTokenExpiringSoon:Q,"
_VIRGIN_EPHEMERAL_I = "return yield(0,r.Zn)({currentToken:l,ephemeralToken:i,isTokenExpiringSoon:a,"
_VIRGIN_FACTORY = (
    'function A(e){var t;const n=null!==(t=e.store)&&void 0!==t?t:"default";'
    'return"memory"===n?new m:"file"===n?new a(e.domain):'
    '"darwin"===(0,r.platform)()?new u(e.domain):new a(e.domain)}'
)


def _load_gz(path: Path) -> str:
    assert path.is_file(), f"missing fixture: {path}"
    return gzip.decompress(path.read_bytes()).decode("utf-8")


@pytest.fixture(scope="module")
def virgin_index() -> str:
    text = _load_gz(_INDEX_GZ)
    assert "agentcli-hot-auth" not in text
    assert _VIRGIN_CACHE_SHORT in text
    return text


@pytest.fixture(scope="module")
def virgin_uichunk() -> str:
    text = _load_gz(_UICHUNK_GZ)
    assert "agentcli-" not in text
    assert _STATUS_INTERVAL_OLD in text
    assert _FOOTER_KEEP_OLD in text
    assert _SLASH_ANCHOR in text
    assert 'ue.push({id:"sc"' not in text
    return text


def _virgin_replacements() -> list[tuple[str, str]]:
    """仅「上游原串 → 补丁」条目，排除已补丁中间态的升级路径。"""
    return [(old, new) for old, new in _REPLACEMENTS if "agentcli-hot-auth" not in old]


def test_fixture_files_exist() -> None:
    assert _INDEX_GZ.is_file()
    assert _UICHUNK_GZ.is_file()
    assert (_FIXTURE_DIR / "VERSION.txt").is_file()


def test_virgin_index_contains_all_hot_auth_sources(virgin_index: str) -> None:
    missing = [old[:72] for old, _ in _virgin_replacements() if old not in virgin_index]
    assert missing == [], f"virgin index 缺少 {len(missing)} 条原串: {missing[:3]}"


def test_hot_auth_on_virgin_index_matches_expectations(virgin_index: str) -> None:
    out, hits = apply_hot_auth_replacements(virgin_index)
    assert hits >= len(_virgin_replacements())
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
    # 禁止残留
    assert _VIRGIN_CACHE_SHORT not in out
    assert _VIRGIN_EPHEMERAL_R not in out
    assert _VIRGIN_EPHEMERAL_I not in out
    assert _VIRGIN_FACTORY not in out
    assert "ephemeralToken:R," not in out
    assert "setEphemeralToken:e=>{R=e}" not in out
    assert "this.cachedAccessToken=t.accessToken" not in out


def test_hot_auth_idempotent_on_virgin(virgin_index: str) -> None:
    once, hits1 = apply_hot_auth_replacements(virgin_index)
    twice, hits2 = apply_hot_auth_replacements(once)
    assert once == twice
    assert hits2 >= hits1


def test_each_virgin_old_becomes_new(virgin_index: str) -> None:
    for old, new in _virgin_replacements():
        assert old in virgin_index
        patched, hits = apply_hot_auth_replacements(old)
        assert hits >= 1
        assert new in patched
        assert old not in patched


def test_uichunk_status_footer_slash_on_virgin(virgin_uichunk: str) -> None:
    from patches.cursor.cursor_chunks import apply_statusline_interval_text

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
    assert _SLASH_ANCHOR in slash  # inject 末尾仍含 anchor


def test_compile_cache_ps1_snippet() -> None:
    assert "NODE_COMPILE_CACHE" in _COMPILE_CACHE_OLD
    assert "agentcli-hot-auth" in _COMPILE_CACHE_NEW
    assert "Remove-Item Env:NODE_COMPILE_CACHE" in _COMPILE_CACHE_NEW
    out = _COMPILE_CACHE_OLD.replace(_COMPILE_CACHE_OLD, _COMPILE_CACHE_NEW, 1)
    assert out == _COMPILE_CACHE_NEW


def test_metadata() -> None:
    p = CursorAgentPatch()
    assert p.metadata.name == "cursor-agent"
    assert "auto" in p.metadata.tags
    assert "statusline" in p.metadata.tags
    assert "slash" in p.metadata.tags
    assert p.metadata.version >= "2.3.5"


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


def _build_temp_virgin_bundle(
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


def _patch_paths(monkeypatch: pytest.MonkeyPatch, version: Path, root: Path) -> None:
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


def test_patchops_on_temp_virgin_bundle(
    virgin_index: str, virgin_uichunk: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """在临时目录还原 virgin bundle，跑 hot-auth / UI chunk / ps1 补丁并断言。"""
    root, version, index, chunk = _build_temp_virgin_bundle(
        tmp_path, virgin_index, virgin_uichunk
    )
    _patch_paths(monkeypatch, version, root)

    hot_hits, _, _ = ops.patch_hot_auth(index, dry_run=False)
    assert hot_hits >= len(_virgin_replacements())
    patched_index = index.read_text(encoding="utf-8")
    assert MARKER in patched_index and EPHEMERAL_NULL_MARKER in patched_index
    assert DISK_MARKER in patched_index
    assert _VIRGIN_CACHE_SHORT not in patched_index

    iv_hits, _, _ = ops.patch_statusline_interval(version, dry_run=False)
    ft_hits, _, _ = ops.patch_footer_keep(version, dry_run=False)
    sl_hits, _, _ = ops._inject_slash(version, dry_run=False)
    assert iv_hits >= 1 and ft_hits >= 1 and sl_hits >= 1
    chunk_text = chunk.read_text(encoding="utf-8")
    assert STATUS_INTERVAL_MARKER in chunk_text and "_scPl.current" in chunk_text
    assert "}),[b,w,S,x]" in chunk_text and FOOTER_KEEP_MARKER in chunk_text
    assert SLASH_MARKER in chunk_text
    assert "setInterval((()=>C(E.payload)),w)" not in chunk_text

    ps1_hits, _, _ = ops.patch_compile_cache_ps1(root, dry_run=False)
    assert ps1_hits >= 1
    assert "Remove-Item Env:NODE_COMPILE_CACHE" in (
        root / "cursor-agent.ps1"
    ).read_text(encoding="utf-8")

    status = CursorAgentPatch().check(version)
    assert status in (PatchStatus.PARTIAL, PatchStatus.APPLIED)


def test_markers() -> None:
    assert MARKER.startswith("/*") and MARKER.endswith("*/")
    assert STATUS_INTERVAL_MARKER.startswith("/*") and FOOTER_KEEP_MARKER.startswith("/*")
    assert "agentcli-sc-auto-boot" in BOOT_MARKER

def test_unix_wrapper_and_launchers(
    virgin_index: str, virgin_uichunk: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, version, _index, _chunk = _build_temp_virgin_bundle(
        tmp_path, virgin_index, virgin_uichunk
    )
    agent = version / "cursor-agent"
    agent.write_bytes(b"\x7fELF fake-binary")
    _patch_paths(monkeypatch, version, root)
    monkeypatch.setattr(
        "patches.cursor.cursor_agent._is_windows", lambda: False
    )

    from patches.cursor.cursor_agent import _install_sc_launchers

    installed = _install_sc_launchers(root)
    assert (root / "sc").is_file()
    assert (root / "sc-statusline").is_file()
    assert (root / "sc-autoboot.sh").is_file()
    assert "sc.statusline_fast" in (root / "sc-statusline").read_text(encoding="utf-8")
    assert not (root / "sc-statusline").read_bytes().startswith(b"\xef\xbb\xbf")
    assert len(installed) == 3

    ok, files, _ = ops.patch_unix_wrapper(version, dry_run=False)
    assert ok
    assert (version / "cursor-agent.bin").is_file()
    wrap = (version / "cursor-agent").read_text(encoding="utf-8")
    assert "agentcli-sc-auto-boot" in wrap
    assert "cursor-agent.bin" in wrap

    rolled = ops.rollback_unix_wrapper(version)
    assert rolled
    assert (version / "cursor-agent").read_bytes().startswith(b"\x7fELF")
    assert not (version / "cursor-agent.bin").exists()


def test_slash_inject_resolves_unix_sc_root() -> None:
    assert '".local","share","cursor-agent"' in _SLASH_INJECT
    assert '"sc.cmd":"sc"' in _SLASH_INJECT or '?"sc.cmd":"sc"' in _SLASH_INJECT


def test_nudge_inject_and_strip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from patches.cursor.cursor_chunks import (
        NUDGE_MARKER,
        _NUDGE_ANCHOR,
        _NUDGE_INJECT,
        inject_nudge,
        strip_nudge,
    )

    monkeypatch.setattr(
        "patches.cursor.cursor_patchops.assert_js_syntax", lambda path, source: None
    )
    version = tmp_path / "versions" / "t"
    version.mkdir(parents=True)
    chunk = version / "5305.index.js"
    chunk.write_text(
        'br=(0,c.useMemo)((()=>({submitMessage:(e,t)=>{}})),[br])'
        + _NUDGE_ANCHOR
        + "1;",
        encoding="utf-8",
    )
    hits, files, _ = inject_nudge(version, dry_run=False)
    assert hits >= 1 and files
    text = chunk.read_text(encoding="utf-8")
    assert NUDGE_MARKER in text and _NUDGE_INJECT in text
    assert "sc_nudge.json" in text and "submitMessage" in text
    assert "_agentcliNudge=(0,c.useEffect)" in text
    # 不得用分号截断 const 声明链
    assert ";/*agentcli-sc-nudge*/" not in text
    assert ",yr=(0,$.eg)(e,We,br,Wo.inHistory,_o);" not in text
    # 不得在 submit 前 unlink，否则 br 未就绪时会吞掉换号信号
    assert 'if(null==br||"function"!=typeof br.submitMessage)return;' in text
    assert "_fs.unlinkSync(_p);const _t=" not in text
    assert text.index("br.submitMessage(_t)") < text.index("try{_fs.unlinkSync(_p)}")
    sh, sf, _ = strip_nudge(version, dry_run=False)
    assert sh >= 1 and sf
    assert NUDGE_MARKER not in chunk.read_text(encoding="utf-8")
    assert _NUDGE_ANCHOR in chunk.read_text(encoding="utf-8")


def test_disk_bearer_uses_mutable_binding() -> None:
    from patches.cursor.cursor_chunks import _DISK_BEARER_OVERRIDE

    assert "_agentcliBearer=_j.accessToken" in _DISK_BEARER_OVERRIDE
    assert "l=_j.accessToken" not in _DISK_BEARER_OVERRIDE


def test_check_applied_when_optional_uichunk_absent(
    virgin_index: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """本版本没有 interval/footer 片段时，核心补丁齐全应报 APPLIED 而非 PARTIAL。"""
    from patches.cursor.cursor_agent import (
        CursorAgentPatch,
        _UNIX_WRAPPER_MARKER,
        apply_hot_auth_replacements,
    )
    from patches.cursor.cursor_hotauth import MARKER

    root = tmp_path / "cursor-agent"
    version = root / "versions" / "2026.07.23-test"
    version.mkdir(parents=True)
    index = version / "index.js"
    patched, _ = apply_hot_auth_replacements(virgin_index)
    index.write_text(patched, encoding="utf-8")
    # 无 interval/footer OLD 片段的 UI chunk；仅含已注入的 /sc
    (version / "1931.index.js").write_text(
        _SLASH_INJECT + 'ue.push({id:"plugin",title:"Plugin"}',
        encoding="utf-8",
    )
    (root / "sc").write_text("#!/bin/sh\n", encoding="utf-8")
    (root / "sc-statusline").write_text("#!/bin/sh\n", encoding="utf-8")
    (version / "cursor-agent.bin").write_bytes(b"\x7fELF")
    (version / "cursor-agent").write_text(
        f"#!/bin/sh\n{_UNIX_WRAPPER_MARKER}\nexec \"$0.bin\" \"$@\"\n",
        encoding="utf-8",
    )
    _patch_paths(monkeypatch, version, root)
    monkeypatch.setattr(
        "patches.cursor.cursor_agent._is_windows", lambda: False
    )

    assert MARKER in index.read_text(encoding="utf-8")
    assert CursorAgentPatch().check(version) == PatchStatus.APPLIED
