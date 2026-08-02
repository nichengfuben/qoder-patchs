from __future__ import annotations

"""Hot-auth JS replacement table."""

from patches.cursor.cursor_chunks import (
    _AGENTCLI_WAIT_AUTH_FN,
    _CATCH_UPGRADE_CALL,
    _CATCH_UPGRADE_WAIT_INLINE,
    _DISK_BEARER_OVERRIDE,
    _DISK_BEARER_OVERRIDE_LEGACY_L,
    _DISK_BEARER_OVERRIDE_V1,
    _QE_RESUME_PATCHED,
    _QE_RESUME_VIRGIN,
    _QE_UPGRADE_RESUME,
)

_GET_ACCESS_HOT = (
    "getAccessToken(){return o(this,void 0,void 0,(function*(){var e;"
    "/*agentcli-hot-auth*/const t=yield this.readAuthData();"
    "return(null==t?void 0:t.accessToken)?(this.cachedAccessToken=t.accessToken,"
    "this.cachedRefreshToken=null!==(e=t.refreshToken)&&void 0!==e?e:null,t.accessToken)"
    ":(this.cachedAccessToken=null,void 0)}))}"
)
_GET_ACCESS_HOT_TRACE = (
    "getAccessToken(){return o(this,void 0,void 0,(function*(){var e;"
    "/*agentcli-hot-auth*/const t=yield this.readAuthData();"
    "if(!(null==t?void 0:t.accessToken))return this.cachedAccessToken=null,void 0;"
    "this.cachedAccessToken=t.accessToken,"
    "this.cachedRefreshToken=null!==(e=t.refreshToken)&&void 0!==e?e:null;"
    'try{const n=JSON.parse(Buffer.from(String(t.accessToken).split(".")[1],"base64").toString()).sub;'
    's.writeFileSync(this.authFilePath.replace(/auth\\.json$/i,"agentcli-last-bearer.json"),'
    'JSON.stringify({sub:n,ts:Date.now(),pid:process.pid,via:"getAccessToken"}))}catch(e){}'
    "return t.accessToken}))}"
)
# 无缓存版：读盘返回，不赋值 cachedAccessToken / cachedRefreshToken
_GET_ACCESS_NOCACHE = (
    "getAccessToken(){return o(this,void 0,void 0,(function*(){"
    "/*agentcli-hot-auth*/const t=yield this.readAuthData();"
    "if(!(null==t?void 0:t.accessToken))return void 0;"
    'try{const n=JSON.parse(Buffer.from(String(t.accessToken).split(".")[1],"base64").toString()).sub;'
    's.writeFileSync(this.authFilePath.replace(/auth\\.json$/i,"agentcli-last-bearer.json"),'
    'JSON.stringify({sub:n,ts:Date.now(),pid:process.pid,via:"getAccessToken"}))}catch(e){}'
    "return t.accessToken}))}"
)
_GET_REFRESH_NOCACHE = (
    "getRefreshToken(){return o(this,void 0,void 0,(function*(){"
    "/*agentcli-hot-auth*/const t=yield this.readAuthData();"
    "return(null==t?void 0:t.refreshToken)||void 0}))}"
)
_GET_APIKEY_NOCACHE = (
    "getApiKey(){return o(this,void 0,void 0,(function*(){"
    "/*agentcli-hot-auth*/const e=yield this.readAuthData();"
    "return(null==e?void 0:e.apiKey)||void 0}))}"
)
_GET_ALL_NOCACHE = (
    "getAllCredentials(){return o(this,void 0,void 0,(function*(){"
    "/*agentcli-hot-auth*/const e=yield this.readAuthData();"
    "return e?{accessToken:e.accessToken||void 0,refreshToken:e.refreshToken||void 0,"
    "apiKey:e.apiKey||void 0}:{accessToken:void 0,refreshToken:void 0,apiKey:void 0}}))}"
)
_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (
        "getAccessToken(){return o(this,void 0,void 0,(function*(){var e;if(this.cachedAccessToken)return this.cachedAccessToken;const t=yield this.readAuthData();return(null==t?void 0:t.accessToken)?(this.cachedAccessToken=t.accessToken,this.cachedRefreshToken=null!==(e=t.refreshToken)&&void 0!==e?e:null,t.accessToken):void 0}))}",
        _GET_ACCESS_NOCACHE,
    ),
    # 升级：已打 hot-auth（含写 cache / last-bearer）→ 无缓存
    (
        _GET_ACCESS_HOT,
        _GET_ACCESS_NOCACHE,
    ),
    (
        _GET_ACCESS_HOT_TRACE,
        _GET_ACCESS_NOCACHE,
    ),
    # 升级旧版 disk-override（裸 require）→ getBuiltinModule
    (
        '{/*agentcli-hot-auth-disk*/try{const _fs=require("node:fs"),_path=require("node:path"),'
        '_os=require("node:os");const _dir="win32"===process.platform?_path.join('
        'process.env.APPDATA||_path.join(_os.homedir(),"AppData","Roaming"),"Cursor")'
        ':_path.join(_os.homedir(),".cursor");const _auth=_path.join(_dir,"auth.json");'
        'const _j=JSON.parse(_fs.readFileSync(_auth,"utf8"));if(_j&&_j.accessToken)l=_j.accessToken;'
        'try{const _sub=JSON.parse(Buffer.from(String(l).split(".")[1],"base64").toString()).sub;'
        '_fs.writeFileSync(_path.join(_dir,"agentcli-last-bearer.json"),'
        "JSON.stringify({sub:_sub,ts:Date.now(),pid:process.pid}))}catch(_e){}}catch(_e){}}",
        _DISK_BEARER_OVERRIDE,
    ),
    (
        "getRefreshToken(){return o(this,void 0,void 0,(function*(){var e;if(this.cachedRefreshToken)return this.cachedRefreshToken;const t=yield this.readAuthData();return(null==t?void 0:t.refreshToken)?(this.cachedAccessToken=null!==(e=t.accessToken)&&void 0!==e?e:null,this.cachedRefreshToken=t.refreshToken,t.refreshToken):void 0}))}",
        _GET_REFRESH_NOCACHE,
    ),
    (
        "getRefreshToken(){return o(this,void 0,void 0,(function*(){var e;/*agentcli-hot-auth*/const t=yield this.readAuthData();return(null==t?void 0:t.refreshToken)?(this.cachedAccessToken=null!==(e=t.accessToken)&&void 0!==e?e:null,this.cachedRefreshToken=t.refreshToken,t.refreshToken):(this.cachedRefreshToken=null,void 0)}))}",
        _GET_REFRESH_NOCACHE,
    ),
    (
        "getApiKey(){return o(this,void 0,void 0,(function*(){if(this.cachedApiKey)return this.cachedApiKey;const e=yield this.readAuthData();return(null==e?void 0:e.apiKey)?(this.cachedApiKey=e.apiKey,e.apiKey):void 0}))}",
        _GET_APIKEY_NOCACHE,
    ),
    (
        "getApiKey(){return o(this,void 0,void 0,(function*(){/*agentcli-hot-auth*/const e=yield this.readAuthData();return(null==e?void 0:e.apiKey)?(this.cachedApiKey=e.apiKey,e.apiKey):(this.cachedApiKey=null,void 0)}))}",
        _GET_APIKEY_NOCACHE,
    ),
    (
        "getAllCredentials(){return o(this,void 0,void 0,(function*(){if(null!==this.cachedAccessToken&&null!==this.cachedRefreshToken)return{accessToken:this.cachedAccessToken||void 0,refreshToken:this.cachedRefreshToken||void 0,apiKey:this.cachedApiKey||void 0};const e=yield this.readAuthData();return e?(this.cachedAccessToken=e.accessToken||null,this.cachedRefreshToken=e.refreshToken||null,this.cachedApiKey=e.apiKey||null,{accessToken:e.accessToken||void 0,refreshToken:e.refreshToken||void 0,apiKey:e.apiKey||void 0}):{accessToken:void 0,refreshToken:void 0,apiKey:void 0}}))}",
        _GET_ALL_NOCACHE,
    ),
    (
        "getAllCredentials(){return o(this,void 0,void 0,(function*(){/*agentcli-hot-auth*/const e=yield this.readAuthData();return e?(this.cachedAccessToken=e.accessToken||null,this.cachedRefreshToken=e.refreshToken||null,this.cachedApiKey=e.apiKey||null,{accessToken:e.accessToken||void 0,refreshToken:e.refreshToken||void 0,apiKey:e.apiKey||void 0}):(this.cachedAccessToken=null,this.cachedRefreshToken=null,this.cachedApiKey=null,{accessToken:void 0,refreshToken:void 0,apiKey:void 0})}))}",
        _GET_ALL_NOCACHE,
    ),
    # secret/keychain：一律空（工厂已强制 file；禁止钥匙串缓存）
    (
        "getAccessToken(){return c(this,void 0,void 0,(function*(){if(this.cachedAccessToken)return this.cachedAccessToken;const e=yield this.getSecret(this.accessTokenService);return e?(this.cachedAccessToken=e,e):void 0}))}",
        "getAccessToken(){return c(this,void 0,void 0,(function*(){/*agentcli-hot-auth*/return void 0}))}",
    ),
    (
        "getAccessToken(){return c(this,void 0,void 0,(function*(){/*agentcli-hot-auth*/const e=yield this.getSecret(this.accessTokenService);return e?(this.cachedAccessToken=e,e):(this.cachedAccessToken=null,void 0)}))}",
        "getAccessToken(){return c(this,void 0,void 0,(function*(){/*agentcli-hot-auth*/return void 0}))}",
    ),
    (
        "getRefreshToken(){return c(this,void 0,void 0,(function*(){if(this.cachedRefreshToken)return this.cachedRefreshToken;const e=yield this.getSecret(this.refreshTokenService);return e?(this.cachedRefreshToken=e,e):void 0}))}",
        "getRefreshToken(){return c(this,void 0,void 0,(function*(){/*agentcli-hot-auth*/return void 0}))}",
    ),
    (
        "getRefreshToken(){return c(this,void 0,void 0,(function*(){/*agentcli-hot-auth*/const e=yield this.getSecret(this.refreshTokenService);return e?(this.cachedRefreshToken=e,e):(this.cachedRefreshToken=null,void 0)}))}",
        "getRefreshToken(){return c(this,void 0,void 0,(function*(){/*agentcli-hot-auth*/return void 0}))}",
    ),
    (
        "getApiKey(){return c(this,void 0,void 0,(function*(){if(this.cachedApiKey)return this.cachedApiKey;const e=yield this.getSecret(this.apiKeyService);return e?(this.cachedApiKey=e,e):void 0}))}",
        "getApiKey(){return c(this,void 0,void 0,(function*(){/*agentcli-hot-auth*/return void 0}))}",
    ),
    (
        "getApiKey(){return c(this,void 0,void 0,(function*(){/*agentcli-hot-auth*/const e=yield this.getSecret(this.apiKeyService);return e?(this.cachedApiKey=e,e):(this.cachedApiKey=null,void 0)}))}",
        "getApiKey(){return c(this,void 0,void 0,(function*(){/*agentcli-hot-auth*/return void 0}))}",
    ),
    (
        "getAllCredentials(){return c(this,void 0,void 0,(function*(){if(null!==this.cachedAccessToken&&null!==this.cachedRefreshToken)return{accessToken:this.cachedAccessToken||void 0,refreshToken:this.cachedRefreshToken||void 0,apiKey:this.cachedApiKey||void 0};const[e,t,n]=yield Promise.all([null!==this.cachedAccessToken?Promise.resolve(this.cachedAccessToken||void 0):this.getSecret(this.accessTokenService),null!==this.cachedRefreshToken?Promise.resolve(this.cachedRefreshToken||void 0):this.getSecret(this.refreshTokenService),null!==this.cachedApiKey?Promise.resolve(this.cachedApiKey||void 0):this.getSecret(this.apiKeyService)]);return this.cachedAccessToken=e||null,this.cachedRefreshToken=t||null,this.cachedApiKey=n||null,{accessToken:e,refreshToken:t,apiKey:n}}))}",
        "getAllCredentials(){return c(this,void 0,void 0,(function*(){/*agentcli-hot-auth*/return{accessToken:void 0,refreshToken:void 0,apiKey:void 0}}))}",
    ),
    (
        "getAllCredentials(){return c(this,void 0,void 0,(function*(){/*agentcli-hot-auth*/const[e,t,n]=yield Promise.all([this.getSecret(this.accessTokenService),this.getSecret(this.refreshTokenService),this.getSecret(this.apiKeyService)]);return this.cachedAccessToken=e||null,this.cachedRefreshToken=t||null,this.cachedApiKey=n||null,{accessToken:e,refreshToken:t,apiKey:n}}))}",
        "getAllCredentials(){return c(this,void 0,void 0,(function*(){/*agentcli-hot-auth*/return{accessToken:void 0,refreshToken:void 0,apiKey:void 0}}))}",
    ),
    # memory AuthStorage：禁止返回进程内字段
    (
        "getAccessToken(){return d(this,void 0,void 0,(function*(){var e;return null!==(e=this.accessToken)&&void 0!==e?e:void 0}))}",
        "getAccessToken(){return d(this,void 0,void 0,(function*(){/*agentcli-hot-auth*/return void 0}))}",
    ),
    (
        "getRefreshToken(){return d(this,void 0,void 0,(function*(){var e;return null!==(e=this.refreshToken)&&void 0!==e?e:void 0}))}",
        "getRefreshToken(){return d(this,void 0,void 0,(function*(){/*agentcli-hot-auth*/return void 0}))}",
    ),
    (
        "getApiKey(){return d(this,void 0,void 0,(function*(){var e;return null!==(e=this.apiKey)&&void 0!==e?e:void 0}))}",
        "getApiKey(){return d(this,void 0,void 0,(function*(){/*agentcli-hot-auth*/return void 0}))}",
    ),
    (
        "getAllCredentials(){return d(this,void 0,void 0,(function*(){var e,t,n;return{accessToken:null!==(e=this.accessToken)&&void 0!==e?e:void 0,refreshToken:null!==(t=this.refreshToken)&&void 0!==t?t:void 0,apiKey:null!==(n=this.apiKey)&&void 0!==n?n:void 0}}))}",
        "getAllCredentials(){return d(this,void 0,void 0,(function*(){/*agentcli-hot-auth*/return{accessToken:void 0,refreshToken:void 0,apiKey:void 0}}))}",
    ),
    # setAuthentication：auth-refresh 不得覆盖 sc 刚写入的外部换号
    (
        "setAuthentication(e,t,n){return o(this,void 0,void 0,(function*(){const r=yield this.readAuthData(),s={accessToken:e,refreshToken:t,apiKey:n,bedrockCredentials:null==r?void 0:r.bedrockCredentials};yield this.writeAuthData(s),this.cachedAccessToken=e,this.cachedRefreshToken=t,this.cachedApiKey=null!=n?n:null}))}",
        "setAuthentication(e,t,n){return o(this,void 0,void 0,(function*(){const r=yield this.readAuthData();"
        "/*agentcli-hot-auth*/try{const _d=null==r?void 0:r.accessToken;if(_d&&_d!==e){"
        'const _a=JSON.parse(Buffer.from(String(_d).split(".")[1],"base64").toString()).sub;'
        'const _b=JSON.parse(Buffer.from(String(e).split(".")[1],"base64").toString()).sub;'
        "if(_a&&_b&&_a!==_b)return this.cachedAccessToken=_d,this.cachedRefreshToken=null==r?void 0:r.refreshToken,"
        "this.cachedApiKey=null==r?void 0:r.apiKey,void 0}}catch(_e){}"
        "const s={accessToken:e,refreshToken:t,apiKey:n,bedrockCredentials:null==r?void 0:r.bedrockCredentials};"
        "yield this.writeAuthData(s),this.cachedAccessToken=e,this.cachedRefreshToken=t,this.cachedApiKey=null!=n?n:null}))}",
    ),
    # 额度 ActionRequiredError(upgrade/payment)：auth.json 换号后内部 ResumeAction 重试，不发 UI「继续」
    # 锚点含上文 return t}，避免二次 apply 时裸 function Qe 误匹配已注入区域
    (
        "return t}"
        + _AGENTCLI_WAIT_AUTH_FN
        + "function Qe(e,t,n,r,s,i,o,a,l){",
        "return t}"
        + _AGENTCLI_WAIT_AUTH_FN
        + "function Qe(e,t,n,r,s,i,o,a,l){",
    ),
    (
        "return t}function Qe(e,t,n,r,s,i,o,a,l){",
        "return t}"
        + _AGENTCLI_WAIT_AUTH_FN
        + "function Qe(e,t,n,r,s,i,o,a,l){",
    ),
    (
        _QE_RESUME_PATCHED,
        _QE_RESUME_PATCHED,
    ),
    (
        _QE_RESUME_VIRGIN,
        _QE_RESUME_PATCHED,
    ),
    (
        "}catch(t){"
        + _CATCH_UPGRADE_CALL
        + "const n=null!==(_=null===(f=d.endlessRetries)||void 0===f?void 0:f.call(d))&&void 0!==_&&_,r=Re(t),s=Qe(t,",
        "}catch(t){"
        + _CATCH_UPGRADE_CALL
        + "const n=null!==(_=null===(f=d.endlessRetries)||void 0===f?void 0:f.call(d))&&void 0!==_&&_,r=Re(t),s=Qe(t,",
    ),
    (
        "}catch(t){const n=null!==(_=null===(f=d.endlessRetries)||void 0===f?void 0:f.call(d))&&void 0!==_&&_,r=Re(t),s=Qe(t,",
        "}catch(t){"
        + _CATCH_UPGRADE_CALL
        + "const n=null!==(_=null===(f=d.endlessRetries)||void 0===f?void 0:f.call(d))&&void 0!==_&&_,r=Re(t),s=Qe(t,",
    ),
    # 升级：旧版 catch 内联 wait（语法错误）→ 函数调用
    (
        "}catch(t){"
        + _CATCH_UPGRADE_WAIT_INLINE
        + "const n=null!==(_=null===(f=d.endlessRetries)||void 0===f?void 0:f.call(d))&&void 0!==_&&_,r=Re(t),s=Qe(t,",
        "}catch(t){"
        + _CATCH_UPGRADE_CALL
        + "const n=null!==(_=null===(f=d.endlessRetries)||void 0===f?void 0:f.call(d))&&void 0!==_&&_,r=Re(t),s=Qe(t,",
    ),
    # 升级 disk-override：记录本轮 Run 的 sub，供换号检测
    (
        _DISK_BEARER_OVERRIDE_V1,
        _DISK_BEARER_OVERRIDE,
    ),
    # 工厂：一律 file AuthStorage，保证与 sc 写入的 auth.json 同源热读
    (
        'function A(e){var t;const n=null!==(t=e.store)&&void 0!==t?t:"default";return"memory"===n?new m:"file"===n?new a(e.domain):"darwin"===(0,r.platform)()?new u(e.domain):new a(e.domain)}',
        "function A(e){/*agentcli-hot-auth*/return new a(e.domain)}",
    ),
    # 兼容已应用旧版「保留 memory」工厂补丁的回滚/再应用
    (
        'function A(e){var t;const n=null!==(t=e.store)&&void 0!==t?t:"default";return"memory"===n?new m:new a(e.domain)/*agentcli-hot-auth*/}',
        "function A(e){/*agentcli-hot-auth*/return new a(e.domain)}",
    ),
    # auth-refresh：模块级 ephemeral / apiKeyOverride 永不生效
    (
        "function l(e){i=null!=e?e:null}",
        "function l(e){/*agentcli-hot-auth*/i=null}",
    ),
    (
        "function c(e){o=null!=e?e:null}",
        "function c(e){/*agentcli-hot-auth*/o=null}",
    ),
    # uX：Bearer 解析时 ephemeral 恒为 null，只信 getAccessToken()（读盘）
    (
        "return yield(0,r.Zn)({currentToken:l,ephemeralToken:i,isTokenExpiringSoon:a,",
        "return yield(0,r.Zn)({currentToken:l,ephemeralToken:null/*agentcli-hot-auth*/,isTokenExpiringSoon:a,",
    ),
    # Zn：忽略 ephemeral 回落；有盘上 token 且未过期则直接用，否则 refresh
    (
        "function k(e){return v(this,void 0,void 0,(function*(){const{currentToken:t,ephemeralToken:n,isTokenExpiringSoon:r,refreshToken:s}=e;if(!t){if(n){if(!r(n))return n;const e=yield s();return null!=e?e:n}return yield s()}if(!r(t))return t;return(yield s())||(n&&!r(n)?n:t)}))}",
        "function k(e){return v(this,void 0,void 0,(function*(){const{currentToken:t,isTokenExpiringSoon:r,refreshToken:s}=e;/*agentcli-hot-auth*/if(t&&!r(t))return t;if(t){const e=yield s();return null!=e?e:t}return yield s()}))}",
    ),
    # 登录成功写入 ephemeral 时改为清掉，只依赖 persist→auth.json
    (
        "function I(e){return v(this,void 0,void 0,(function*(){const{accessToken:t,persist:n,setEphemeralToken:r}=e;r(t),yield n()}))}",
        "function I(e){return v(this,void 0,void 0,(function*(){const{accessToken:t,persist:n,setEphemeralToken:r}=e;/*agentcli-hot-auth*/r(null),yield n()}))}",
    ),
    # 第二套内联 auth（agent 主链路）：ephemeralToken:R —— 此前只补了 auth-refresh 的 i
    (
        "ephemeralToken:R,isTokenExpiringSoon:Q,",
        "ephemeralToken:null/*agentcli-hot-auth*/,isTokenExpiringSoon:Q,",
    ),
    (
        "setEphemeralToken:e=>{R=e}",
        "setEphemeralToken:e=>{/*agentcli-hot-auth*/R=null}",
    ),
    # 核弹：每次设 Bearer 前同步读盘；用 var _agentcliBearer（外层常是 const l，不能赋值）
    (
        'l=yield(0,B.uX)(e,a);null!=l&&s.header.set("authorization",`Bearer ${l}`);',
        'l=yield(0,B.uX)(e,a);var _agentcliBearer=l;'
        + _DISK_BEARER_OVERRIDE
        + 'null!=_agentcliBearer&&s.header.set("authorization",`Bearer ${_agentcliBearer}`);',
    ),
    (
        '}(e,a);null!=l&&s.header.set("authorization",`Bearer ${l}`);',
        '}(e,a);var _agentcliBearer=l;'
        + _DISK_BEARER_OVERRIDE
        + 'null!=_agentcliBearer&&s.header.set("authorization",`Bearer ${_agentcliBearer}`);',
    ),
    # 升级：旧 disk-override 给 const l 赋值（静默失败）→ _agentcliBearer
    (
        'l=yield(0,B.uX)(e,a);'
        + _DISK_BEARER_OVERRIDE_LEGACY_L
        + 'null!=l&&s.header.set("authorization",`Bearer ${l}`);',
        'l=yield(0,B.uX)(e,a);var _agentcliBearer=l;'
        + _DISK_BEARER_OVERRIDE
        + 'null!=_agentcliBearer&&s.header.set("authorization",`Bearer ${_agentcliBearer}`);',
    ),
    (
        '}(e,a);'
        + _DISK_BEARER_OVERRIDE_LEGACY_L
        + 'null!=l&&s.header.set("authorization",`Bearer ${l}`);',
        '}(e,a);var _agentcliBearer=l;'
        + _DISK_BEARER_OVERRIDE
        + 'null!=_agentcliBearer&&s.header.set("authorization",`Bearer ${_agentcliBearer}`);',
    ),
    # local-worker / indexing：se(credentialManager) 路径同样强制读盘
    (
        'function se(e){return t=>n=>ne(this,void 0,void 0,(function*(){const r=yield e.getAccessToken();if(!r)throw new Error("No access token found");n.header.set("authorization",`Bearer ${r}`);',
        'function se(e){return t=>n=>ne(this,void 0,void 0,(function*(){var r=yield e.getAccessToken();'
        '/*agentcli-hot-auth*/try{const _fs=(process.getBuiltinModule&&(process.getBuiltinModule("node:fs")||process.getBuiltinModule("fs")))||require("node:fs"),'
        '_path=(process.getBuiltinModule&&(process.getBuiltinModule("node:path")||process.getBuiltinModule("path")))||require("node:path"),'
        '_os=(process.getBuiltinModule&&(process.getBuiltinModule("node:os")||process.getBuiltinModule("os")))||require("node:os");'
        'const _dir="win32"===process.platform?_path.join(process.env.APPDATA||_path.join(_os.homedir(),"AppData","Roaming"),"Cursor"):_path.join(_os.homedir(),".cursor");'
        'const _j=JSON.parse(_fs.readFileSync(_path.join(_dir,"auth.json"),"utf8"));if(_j&&_j.accessToken)r=_j.accessToken;'
        '_fs.writeFileSync(_path.join(_dir,"agentcli-last-bearer.json"),JSON.stringify({sub:JSON.parse(Buffer.from(String(r).split(".")[1],"base64").toString()).sub,ts:Date.now(),pid:process.pid,via:"se"}))}catch(_e){}'
        'if(!r)throw new Error("No access token found");n.header.set("authorization",`Bearer ${r}`);',
    ),
    # telemetry / privacy / getMe 拦截器：credentialManager.getAccessToken 后同样强制读盘
    (
        'const r=yield e.credentialManager.getAccessToken();return r&&n.header.set("authorization",`Bearer ${r}`),t(n)',
        'var r=yield e.credentialManager.getAccessToken();'
        '/*agentcli-hot-auth*/try{const _fs=(process.getBuiltinModule&&(process.getBuiltinModule("node:fs")||process.getBuiltinModule("fs")))||require("node:fs"),'
        '_path=(process.getBuiltinModule&&(process.getBuiltinModule("node:path")||process.getBuiltinModule("path")))||require("node:path"),'
        '_os=(process.getBuiltinModule&&(process.getBuiltinModule("node:os")||process.getBuiltinModule("os")))||require("node:os");'
        'const _dir="win32"===process.platform?_path.join(process.env.APPDATA||_path.join(_os.homedir(),"AppData","Roaming"),"Cursor"):_path.join(_os.homedir(),".cursor");'
        'const _j=JSON.parse(_fs.readFileSync(_path.join(_dir,"auth.json"),"utf8"));if(_j&&_j.accessToken)r=_j.accessToken;'
        '_fs.writeFileSync(_path.join(_dir,"agentcli-last-bearer.json"),JSON.stringify({sub:JSON.parse(Buffer.from(String(r).split(".")[1],"base64").toString()).sub,ts:Date.now(),pid:process.pid,via:"cm-t"}))}catch(_e){}'
        'return r&&n.header.set("authorization",`Bearer ${r}`),t(n)',
    ),
    (
        'const s=yield e.credentialManager.getAccessToken();return s&&n.header.set("authorization",`Bearer ${s}`),(0,r._5)(n.header),t(n)',
        'var s=yield e.credentialManager.getAccessToken();'
        '/*agentcli-hot-auth*/try{const _fs=(process.getBuiltinModule&&(process.getBuiltinModule("node:fs")||process.getBuiltinModule("fs")))||require("node:fs"),'
        '_path=(process.getBuiltinModule&&(process.getBuiltinModule("node:path")||process.getBuiltinModule("path")))||require("node:path"),'
        '_os=(process.getBuiltinModule&&(process.getBuiltinModule("node:os")||process.getBuiltinModule("os")))||require("node:os");'
        'const _dir="win32"===process.platform?_path.join(process.env.APPDATA||_path.join(_os.homedir(),"AppData","Roaming"),"Cursor"):_path.join(_os.homedir(),".cursor");'
        'const _j=JSON.parse(_fs.readFileSync(_path.join(_dir,"auth.json"),"utf8"));if(_j&&_j.accessToken)s=_j.accessToken;'
        '_fs.writeFileSync(_path.join(_dir,"agentcli-last-bearer.json"),JSON.stringify({sub:JSON.parse(Buffer.from(String(s).split(".")[1],"base64").toString()).sub,ts:Date.now(),pid:process.pid,via:"cm-s"}))}catch(_e){}'
        'return s&&n.header.set("authorization",`Bearer ${s}`),(0,r._5)(n.header),t(n)',
    ),
    (
        'const r=yield e.credentialManager.getAccessToken();return r&&n.header.set("authorization",`Bearer ${r}`),o(n.header),t(n)',
        'var r=yield e.credentialManager.getAccessToken();'
        '/*agentcli-hot-auth*/try{const _fs=(process.getBuiltinModule&&(process.getBuiltinModule("node:fs")||process.getBuiltinModule("fs")))||require("node:fs"),'
        '_path=(process.getBuiltinModule&&(process.getBuiltinModule("node:path")||process.getBuiltinModule("path")))||require("node:path"),'
        '_os=(process.getBuiltinModule&&(process.getBuiltinModule("node:os")||process.getBuiltinModule("os")))||require("node:os");'
        'const _dir="win32"===process.platform?_path.join(process.env.APPDATA||_path.join(_os.homedir(),"AppData","Roaming"),"Cursor"):_path.join(_os.homedir(),".cursor");'
        'const _j=JSON.parse(_fs.readFileSync(_path.join(_dir,"auth.json"),"utf8"));if(_j&&_j.accessToken)r=_j.accessToken;'
        '_fs.writeFileSync(_path.join(_dir,"agentcli-last-bearer.json"),JSON.stringify({sub:JSON.parse(Buffer.from(String(r).split(".")[1],"base64").toString()).sub,ts:Date.now(),pid:process.pid,via:"cm-o"}))}catch(_e){}'
        'return r&&n.header.set("authorization",`Bearer ${r}`),o(n.header),t(n)',
    ),
)

