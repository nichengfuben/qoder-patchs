"""Tests for patches.cursor_agent — 用上游原串验证 hot-auth 替换。"""

from __future__ import annotations

from patches.cursor_agent import (
    BOOT_MARKER,
    DISK_MARKER,
    EPHEMERAL_NULL_MARKER,
    FOOTER_KEEP_MARKER,
    MARKER,
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


# 上游 minify 原串（与 2026.07.23-e383d2b index.js 对齐；勿改空格）
_ORIG_FILE_GET_ACCESS = (
    "getAccessToken(){return o(this,void 0,void 0,(function*(){var e;"
    "if(this.cachedAccessToken)return this.cachedAccessToken;"
    "const t=yield this.readAuthData();"
    "return(null==t?void 0:t.accessToken)?(this.cachedAccessToken=t.accessToken,"
    "this.cachedRefreshToken=null!==(e=t.refreshToken)&&void 0!==e?e:null,t.accessToken):void 0}))}"
)
_ORIG_FACTORY = (
    'function A(e){var t;const n=null!==(t=e.store)&&void 0!==t?t:"default";'
    'return"memory"===n?new m:"file"===n?new a(e.domain):'
    '"darwin"===(0,r.platform)()?new u(e.domain):new a(e.domain)}'
)
_ORIG_UX_ZN = "return yield(0,r.Zn)({currentToken:l,ephemeralToken:i,isTokenExpiringSoon:a,"
_ORIG_EPHEMERAL_R = "ephemeralToken:R,isTokenExpiringSoon:Q,"
_ORIG_SET_R = "setEphemeralToken:e=>{R=e}"
_ORIG_BEARER_UX = 'l=yield(0,B.uX)(e,a);null!=l&&s.header.set("authorization",`Bearer ${l}`);'
_ORIG_BEARER_INLINE = '}(e,a);null!=l&&s.header.set("authorization",`Bearer ${l}`);'
_ORIG_ZN = (
    "function k(e){return v(this,void 0,void 0,(function*(){"
    "const{currentToken:t,ephemeralToken:n,isTokenExpiringSoon:r,refreshToken:s}=e;"
    "if(!t){if(n){if(!r(n))return n;const e=yield s();return null!=e?e:n}"
    "return yield s()}if(!r(t))return t;return(yield s())||(n&&!r(n)?n:t)}))}"
)
_ORIG_SET_EPHEMERAL = "function l(e){i=null!=e?e:null}"
_ORIG_SET_APIKEY = "function c(e){o=null!=e?e:null}"
_ORIG_PERSIST_EPHEMERAL = (
    "function I(e){return v(this,void 0,void 0,(function*(){"
    "const{accessToken:t,persist:n,setEphemeralToken:r}=e;r(t),yield n()}))}"
)
_ORIG_MEMORY_GET_ACCESS = (
    "getAccessToken(){return d(this,void 0,void 0,(function*(){"
    "var e;return null!==(e=this.accessToken)&&void 0!==e?e:void 0}))}"
)
_ORIG_KEYCHAIN_GET_ALL = (
    "getAllCredentials(){return c(this,void 0,void 0,(function*(){"
    "if(null!==this.cachedAccessToken&&null!==this.cachedRefreshToken)"
    "return{accessToken:this.cachedAccessToken||void 0,"
    "refreshToken:this.cachedRefreshToken||void 0,apiKey:this.cachedApiKey||void 0};"
    "const[e,t,n]=yield Promise.all(["
    "null!==this.cachedAccessToken?Promise.resolve(this.cachedAccessToken||void 0)"
    ":this.getSecret(this.accessTokenService),"
    "null!==this.cachedRefreshToken?Promise.resolve(this.cachedRefreshToken||void 0)"
    ":this.getSecret(this.refreshTokenService),"
    "null!==this.cachedApiKey?Promise.resolve(this.cachedApiKey||void 0)"
    ":this.getSecret(this.apiKeyService)]);"
    "return this.cachedAccessToken=e||null,this.cachedRefreshToken=t||null,"
    "this.cachedApiKey=n||null,{accessToken:e,refreshToken:t,apiKey:n}}))}"
)

_FIXTURE_ORIGINAL = "\n".join(
    [
        _ORIG_FILE_GET_ACCESS,
        _ORIG_FACTORY,
        _ORIG_UX_ZN,
        _ORIG_ZN,
        _ORIG_SET_EPHEMERAL,
        _ORIG_SET_APIKEY,
        _ORIG_PERSIST_EPHEMERAL,
        _ORIG_MEMORY_GET_ACCESS,
        _ORIG_KEYCHAIN_GET_ALL,
        _ORIG_EPHEMERAL_R,
        _ORIG_SET_R,
        _ORIG_BEARER_UX,
        _ORIG_BEARER_INLINE,
    ]
)


def test_hot_auth_marker() -> None:
    assert MARKER.startswith("/*") and MARKER.endswith("*/")


def test_status_interval_marker() -> None:
    assert STATUS_INTERVAL_MARKER.startswith("/*") and "status-interval" in STATUS_INTERVAL_MARKER


def test_footer_keep_marker() -> None:
    assert FOOTER_KEEP_MARKER.startswith("/*") and "footer-keep" in FOOTER_KEEP_MARKER


def test_boot_marker() -> None:
    assert "agentcli-sc-auto-boot" in BOOT_MARKER


def test_metadata_includes_statusline_and_slash() -> None:
    p = CursorAgentPatch()
    assert p.metadata.name == "cursor-agent"
    assert "auto" in p.metadata.tags
    assert "statusline" in p.metadata.tags
    assert "slash" in p.metadata.tags
    assert p.metadata.version >= "2.3.5"


def test_find_client_config_requires_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("AGENTCLI_SC_CONFIG_SRC", raising=False)
    assert find_client_config() is None
    src = tmp_path / "config.json"
    src.write_text('{"base_url":"","api_keys":[]}', encoding="utf-8")
    monkeypatch.setenv("AGENTCLI_SC_CONFIG_SRC", str(src))
    path = find_client_config()
    assert path is not None
    assert path.name == "config.json"


def test_apply_hot_auth_on_original_snippets() -> None:
    """原串 → 补丁后：无缓存短路、无 ephemeral、工厂强制 file。"""
    out, hits = apply_hot_auth_replacements(_FIXTURE_ORIGINAL)
    assert hits >= 8
    assert MARKER in out
    assert EPHEMERAL_NULL_MARKER in out
    assert DISK_MARKER in out
    assert _DISK_BEARER_OVERRIDE in out
    assert "ephemeralToken:R," not in out
    assert "setEphemeralToken:e=>{R=e}" not in out
    assert "if(this.cachedAccessToken)return this.cachedAccessToken" not in out
    assert "this.cachedAccessToken=t.accessToken" not in out
    assert "ephemeralToken:i," not in out
    assert "function A(e){/*agentcli-hot-auth*/return new a(e.domain)}" in out
    assert "function l(e){/*agentcli-hot-auth*/i=null}" in out
    assert "function c(e){/*agentcli-hot-auth*/o=null}" in out
    assert "r(null),yield n()" in out
    assert "return null!==(e=this.accessToken)" not in out
    assert "if(null!==this.cachedAccessToken&&null!==this.cachedRefreshToken)return{accessToken:this.cachedAccessToken" not in out
    # Zn 解构不再包含 ephemeralToken
    assert "ephemeralToken:n,isTokenExpiringSoon" not in out
    assert "/*agentcli-hot-auth*/if(t&&!r(t))return t" in out
    assert _GET_ACCESS_NOCACHE.split("/*agentcli-hot-auth*/")[1][:40] in out or "via:\"getAccessToken\"" in out


def test_apply_hot_auth_idempotent() -> None:
    once, hits1 = apply_hot_auth_replacements(_FIXTURE_ORIGINAL)
    twice, hits2 = apply_hot_auth_replacements(once)
    assert once == twice
    assert hits2 >= hits1


def test_each_replacement_old_becomes_new() -> None:
    for old, new in _REPLACEMENTS:
        patched, hits = apply_hot_auth_replacements(old)
        assert hits >= 1
        assert new in patched
        assert old not in patched


def test_compile_cache_ps1_snippet() -> None:
    assert "NODE_COMPILE_CACHE" in _COMPILE_CACHE_OLD
    assert "agentcli-hot-auth" in _COMPILE_CACHE_NEW
    assert "Remove-Item Env:NODE_COMPILE_CACHE" in _COMPILE_CACHE_NEW
    out = _COMPILE_CACHE_OLD.replace(_COMPILE_CACHE_OLD, _COMPILE_CACHE_NEW, 1)
    assert out == _COMPILE_CACHE_NEW


def test_live_bundle_originals_match_or_already_patched() -> None:
    """本机 index.js：要么仍含原串（可补），要么已是补丁目标形态。"""
    from sc.paths import find_cursor_agent_bundle

    bundle = find_cursor_agent_bundle()
    if bundle is None:
        return
    text = (bundle / "index.js").read_text(encoding="utf-8", errors="ignore")
    # 核心原串或已补丁形态至少命中一侧
    assert (
        _ORIG_FILE_GET_ACCESS in text
        or "/*agentcli-hot-auth*/const t=yield this.readAuthData()" in text
    )
    assert (
        _ORIG_UX_ZN in text
        or EPHEMERAL_NULL_MARKER in text
    )
    assert (
        _ORIG_ZN in text
        or "/*agentcli-hot-auth*/if(t&&!r(t))return t" in text
    )
    patched, hits = apply_hot_auth_replacements(text)
    assert hits >= 1
    assert EPHEMERAL_NULL_MARKER in patched
    assert DISK_MARKER in patched
    assert "ephemeralToken:i," not in patched
    assert "ephemeralToken:R," not in patched
