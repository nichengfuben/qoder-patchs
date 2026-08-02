"""Integration tests for cursor-agent patch apply on virgin bundle."""

from __future__ import annotations

from pathlib import Path

import pytest

from patches.cursor.cursor_agent import (
    DISK_MARKER,
    EPHEMERAL_NULL_MARKER,
    FOOTER_KEEP_MARKER,
    MARKER,
    SLASH_MARKER,
    STATUS_INTERVAL_MARKER,
    _DISK_BEARER_OVERRIDE,
    _UNIX_WRAPPER_MARKER,
    CursorAgentPatch,
    apply_hot_auth_replacements,
)
from patches.cursor.cursor_chunks import _SLASH_INJECT
from utils.cursor_nudge import (
    NUDGE_MARKER,
    _NUDGE_ANCHOR,
    _NUDGE_INJECT,
    inject_nudge,
    strip_nudge,
)
from patches.cursor import cursor_patchops as ops
from core.patch_base import PatchStatus

from test.patches.cursoragent.helpers import (
    build_temp_virgin_bundle,
    patch_bundle_paths,
    virgin_replacements,
)

_VIRGIN_CACHE_SHORT = "if(this.cachedAccessToken)return this.cachedAccessToken"


def test_patchops_on_temp_virgin_bundle(
    virgin_index: str, virgin_uichunk: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, version, index, chunk = build_temp_virgin_bundle(
        tmp_path, virgin_index, virgin_uichunk
    )
    patch_bundle_paths(monkeypatch, version, root)

    hot_hits, _, _ = ops.patch_hot_auth(index, dry_run=False)
    assert hot_hits >= len(virgin_replacements())
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


def test_unix_wrapper_and_launchers(
    virgin_index: str, virgin_uichunk: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, version, _index, _chunk = build_temp_virgin_bundle(
        tmp_path, virgin_index, virgin_uichunk
    )
    agent = version / "cursor-agent"
    agent.write_bytes(b"\x7fELF fake-binary")
    patch_bundle_paths(monkeypatch, version, root)
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
    assert _UNIX_WRAPPER_MARKER in wrap
    assert "cursor-agent.bin" in wrap

    rolled = ops.rollback_unix_wrapper(version)
    assert rolled
    assert (version / "cursor-agent").read_bytes().startswith(b"\x7fELF")
    assert not (version / "cursor-agent.bin").exists()


def test_slash_inject_resolves_unix_sc_root() -> None:
    assert '".local","share","cursor-agent"' in _SLASH_INJECT
    assert '"sc.cmd":"sc"' in _SLASH_INJECT or '?"sc.cmd":"sc"' in _SLASH_INJECT


def test_nudge_inject_and_strip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    assert ";/*agentcli-sc-nudge*/" not in text
    assert ",yr=(0,$.eg)(e,We,br,Wo.inHistory,_o);" not in text
    assert 'if(null==br||"function"!=typeof br.submitMessage)return;' in text
    assert "_fs.unlinkSync(_p);const _t=" not in text
    assert text.index("br.submitMessage(_t)") < text.index("try{_fs.unlinkSync(_p)}")
    sh, sf, _ = strip_nudge(version, dry_run=False)
    assert sh >= 1 and sf
    assert NUDGE_MARKER not in chunk.read_text(encoding="utf-8")
    assert _NUDGE_ANCHOR in chunk.read_text(encoding="utf-8")


def test_disk_bearer_uses_mutable_binding() -> None:
    assert "_agentcliBearer=_j.accessToken" in _DISK_BEARER_OVERRIDE
    assert "__agentcliRunSub=_sub" in _DISK_BEARER_OVERRIDE
    assert "l=_j.accessToken" not in _DISK_BEARER_OVERRIDE


def test_check_applied_when_optional_uichunk_absent(
    virgin_index: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "cursor-agent"
    version = root / "versions" / "2026.07.23-test"
    version.mkdir(parents=True)
    index = version / "index.js"
    patched, _ = apply_hot_auth_replacements(virgin_index)
    index.write_text(patched, encoding="utf-8")
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
    patch_bundle_paths(monkeypatch, version, root)
    monkeypatch.setattr(
        "patches.cursor.cursor_agent._is_windows", lambda: False
    )

    assert MARKER in index.read_text(encoding="utf-8")
    assert CursorAgentPatch().check(version) == PatchStatus.APPLIED
