from __future__ import annotations

"""Cursor Agent：auth 热读 + 启动自动 sc auto + statusline + `/sc pull|usage`。

逆向要点：
1. AuthStorage 内存/短路缓存 → 强制每次 readAuthData / getSecret。
2. auth-refresh 模块级 ephemeral / apiKeyOverride → 一律丢弃，Bearer 只信 credentialManager。
3. Zn 解析器不再回落 ephemeral；工厂强制 file AuthStorage。
4. 禁用 NODE_COMPILE_CACHE，避免补丁后仍跑旧字节码。
5. 进入 agent 时由 cursor-agent.cmd 引导后台 ``sc auto``；slash 注入 ``/sc``。
"""

import json
import os
import shutil
import time
from pathlib import Path
from typing import Optional

from loguru import logger

from core.patch_base import PatchBase, PatchMetadata, PatchResult, PatchStatus
from sc.cli_config import merge_status_line
from sc.paths import config_json_path, find_cursor_agent_bundle, find_cursor_agent_root
from utils.paths import get_project_root

MARKER = "/*agentcli-hot-auth*/"
DISK_MARKER = "/*agentcli-hot-auth-disk*/"
SLASH_MARKER = "/*agentcli-sc-slash*/"
BOOT_MARKER = "REM agentcli-sc-auto-boot"
STATUS_INTERVAL_MARKER = "/*agentcli-status-interval*/"
FOOTER_KEEP_MARKER = "/*agentcli-footer-keep*/"
EPHEMERAL_NULL_MARKER = "ephemeralToken:null/*agentcli-hot-auth*/"

# use-status-line.ts：上游把 updateIntervalMs 当成 debounce，不是定时器。
# 空闲时 updateSignal 不变 → statusLine 不刷新 → 时钟卡住。
# 补 setInterval，按 updateIntervalMs（下限 300ms）真正轮询命令。
_STATUS_INTERVAL_OLD = (
    "return(0,l.useEffect)((()=>{var e;return b?(C(E.payload),()=>{var e;"
    "C.cancel(),null===(e=m.current)||void 0===e||e.abort()}):(C.cancel(),"
    "null===(e=m.current)||void 0===e||e.abort(),m.current=null,v.current=null,"
    "void g(null))}),[E,C,b]),{text:p,padding:y}}"
)
_STATUS_INTERVAL_NEW = (
    "return(0,l.useEffect)((()=>{var e;"
    + STATUS_INTERVAL_MARKER
    + "if(!b)return C.cancel(),null===(e=m.current)||void 0===e||e.abort(),"
    "m.current=null,v.current=null,void g(null);"
    "C(E.payload);const t=setInterval((()=>C(E.payload)),w);"
    "return()=>{clearInterval(t),C.cancel(),null===(e=m.current)||void 0===e||e.abort()}"
    "}),[E,C,b,w]),{text:p,padding:y}}"
)

# prompt-footer.tsx：自定义 statusLine 原会替换模型/模式行并隐藏路径行。
# 改为始终渲染原生页脚，SC 命令输出追加在下方。
_FOOTER_KEEP_OLD = (
    'void 0!==y?(0,r.jsx)(l.az,{children:y}):(0,r.jsxs)(l.az,{flexDirection:"row",'
    'justifyContent:"space-between",alignItems:"flex-start",columnGap:2,children:['
    '(0,r.jsxs)(l.az,{flexDirection:"row",gap:1,flexShrink:1,children:['
    'f?(0,r.jsxs)(r.Fragment,{children:[(0,r.jsx)(l.EY,{dimColor:!0,children:f}),'
    '(0,r.jsx)(l.EY,{dimColor:!0,children:"·"})]}):null,'
    '(0,r.jsxs)(l.EY,{dimColor:!0,children:[n,s&&(0,r.jsxs)(l.EY,{dimColor:!0,children:[" ",s]}),'
    'o?(0,r.jsx)(l.EY,{dimColor:!0,children:" · MAX"}):null]}),'
    'a?(0,r.jsxs)(r.Fragment,{children:[(0,r.jsx)(l.EY,{dimColor:!0,children:"·"}),'
    '(0,r.jsx)(l.EY,{dimColor:!0,children:a})]}):null,'
    'p>0&&(0,r.jsxs)(r.Fragment,{children:[(0,r.jsx)(l.EY,{dimColor:!0,children:"·"}),'
    '(0,r.jsxs)(l.EY,{dimColor:!0,children:[p," file",1===p?"":"s"," edited"]})]})]}),'
    'A?(0,r.jsxs)(l.az,{flexShrink:0,paddingRight:1,flexDirection:"row",gap:1,children:['
    'x?(0,r.jsx)(l.EY,{color:"magenta",children:x}):null,'
    'h?(0,r.jsx)(l.EY,{dimColor:!0,children:h}):null]}):null]}),'
    'void 0===y&&b&&E?(0,r.jsx)(l.az,{children:(0,r.jsxs)(l.EY,{dimColor:!0,children:['
    'E,M?` · ${M}`:"",I?` · ${(0,u.N)({text:`#${I.number}`,url:I.url})}`:""]})}):null]'
)
_FOOTER_KEEP_NEW = (
    '(0,r.jsxs)(l.az,{flexDirection:"row",'
    'justifyContent:"space-between",alignItems:"flex-start",columnGap:2,children:['
    '(0,r.jsxs)(l.az,{flexDirection:"row",gap:1,flexShrink:1,children:['
    'f?(0,r.jsxs)(r.Fragment,{children:[(0,r.jsx)(l.EY,{dimColor:!0,children:f}),'
    '(0,r.jsx)(l.EY,{dimColor:!0,children:"·"})]}):null,'
    '(0,r.jsxs)(l.EY,{dimColor:!0,children:[n,s&&(0,r.jsxs)(l.EY,{dimColor:!0,children:[" ",s]}),'
    'o?(0,r.jsx)(l.EY,{dimColor:!0,children:" · MAX"}):null]}),'
    'a?(0,r.jsxs)(r.Fragment,{children:[(0,r.jsx)(l.EY,{dimColor:!0,children:"·"}),'
    '(0,r.jsx)(l.EY,{dimColor:!0,children:a})]}):null,'
    'p>0&&(0,r.jsxs)(r.Fragment,{children:[(0,r.jsx)(l.EY,{dimColor:!0,children:"·"}),'
    '(0,r.jsxs)(l.EY,{dimColor:!0,children:[p," file",1===p?"":"s"," edited"]})]})]}),'
    'A?(0,r.jsxs)(l.az,{flexShrink:0,paddingRight:1,flexDirection:"row",gap:1,children:['
    'x?(0,r.jsx)(l.EY,{color:"magenta",children:x}):null,'
    'h?(0,r.jsx)(l.EY,{dimColor:!0,children:h}):null]}):null]}),'
    'b&&E?(0,r.jsx)(l.az,{children:(0,r.jsxs)(l.EY,{dimColor:!0,children:['
    'E,M?` · ${M}`:"",I?` · ${(0,u.N)({text:`#${I.number}`,url:I.url})}`:""]})}):null,'
    "y?(0,r.jsx)(l.az,{children:y}" + FOOTER_KEEP_MARKER + "):null]"
)

# 紧挨 /mcp 之后、/plugin 之前注入 /sc（仅 pull / usage；异步 spawn 避免卡死 UI）
_SLASH_ANCHOR = 'ue.push({id:"plugin",title:"Plugin"'
_SLASH_INJECT = (
    'ue.push({id:"sc",title:"SC",'
    + SLASH_MARKER
    + 'autoExecuteOnAccept:!0,description:"SC: pull / usage",'
    'ghostText:"[pull|usage]",'
    'boostedAlts:["starcursor"],'
    'args:[{id:"subcommand",required:!0}],'
    "getArgSuggestions:(e,t)=>{"
    'const q=(t[0]||"").trim().toLowerCase();'
    'const opts=[{value:"pull",description:"Pull token → auth.json",autoExecuteOnAccept:!0},'
    '{value:"usage",description:"Refresh usage",autoExecuteOnAccept:!0}];'
    "return q?opts.filter((e=>e.value.startsWith(q))):opts},"
    "run:(e,t,ui)=>se(this,void 0,void 0,(function*(){var o,r;"
    "null===(o=ui.clearInput)||void 0===o||o.call(ui);"
    'const sub=(t[0]||"").trim().toLowerCase();'
    'if(sub!=="pull"&&sub!=="usage"){'
    'null===(r=ui.print)||void 0===r||r.call(ui,[[{text:"usage: /sc pull | /sc usage",color:"red"}]],{minLingerMs:4e3});'
    'return void ui.insertText("")}'
    "let s=\"\",i=1;try{"
    'const cp=n("node:child_process"),path=n("node:path"),fs=n("node:fs");'
    'const root=process.env.LOCALAPPDATA?path.join(process.env.LOCALAPPDATA,"cursor-agent"):"";'
    'const scCmd=root?path.join(root,"sc.cmd"):"";'
    'const env=Object.assign({},process.env,{PYTHONUTF8:"1",PYTHONIOENCODING:"utf-8"});'
    "const result=yield new Promise((resolve)=>{let out=\"\",err=\"\",cmd,args,opts;"
    "if(scCmd&&fs.existsSync(scCmd)){cmd=scCmd;args=[sub];opts={env,shell:!0}}"
    'else{cmd=process.env.AGENTCLI_PYTHON||"python";args=["-m","sc",sub];opts={env,shell:!1}}'
    "const p=cp.spawn(cmd,args,opts);"
    'p.stdout&&p.stdout.on("data",(d)=>{out+=d.toString()});'
    'p.stderr&&p.stderr.on("data",(d)=>{err+=d.toString()});'
    'p.on("error",(e)=>resolve({status:1,text:String(e.message||e)}));'
    'p.on("close",(code)=>resolve({status:null!=code?code:1,text:((out||"")+(err||"")).trim()||("exit "+String(code))}))'
    "});"
    "s=result.text;i=result.status}catch(e){s=String(null!=e.message?e.message:e);i=1}"
    'const lines=s.split(/\\r?\\n/).map((e=>[{text:e,color:i?"red":"green"}]));'
    'null===(r=ui.print)||void 0===r||r.call(ui,lines.length?lines:[[{text:"(no output)",dim:!0}]],'
    '{minLingerMs:8e3}),ui.insertText("")}))}),'
    + _SLASH_ANCHOR
)

# 每次 Authorization 写入前强制 fs.readFileSync(auth.json) 覆盖 token
_DISK_BEARER_OVERRIDE = (
    '{/*agentcli-hot-auth-disk*/try{const _fs=require("node:fs"),_path=require("node:path"),'
    '_os=require("node:os");const _dir="win32"===process.platform?_path.join('
    'process.env.APPDATA||_path.join(_os.homedir(),"AppData","Roaming"),"Cursor")'
    ':_path.join(_os.homedir(),".cursor");const _auth=_path.join(_dir,"auth.json");'
    'const _j=JSON.parse(_fs.readFileSync(_auth,"utf8"));if(_j&&_j.accessToken)l=_j.accessToken;'
    'try{const _sub=JSON.parse(Buffer.from(String(l).split(".")[1],"base64").toString()).sub;'
    '_fs.writeFileSync(_path.join(_dir,"agentcli-last-bearer.json"),'
    'JSON.stringify({sub:_sub,ts:Date.now(),pid:process.pid}))}catch(_e){}}catch(_e){}}'
)

# 原始短路缓存 → 强制每次读盘 / 读 secret；工厂一律 file AuthStorage（忽略 memory/keychain）
# 另：auth-refresh ephemeral / Zn 回落 / keychain getAll 短路 一并掐断。
_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (
        "getAccessToken(){return o(this,void 0,void 0,(function*(){var e;if(this.cachedAccessToken)return this.cachedAccessToken;const t=yield this.readAuthData();return(null==t?void 0:t.accessToken)?(this.cachedAccessToken=t.accessToken,this.cachedRefreshToken=null!==(e=t.refreshToken)&&void 0!==e?e:null,t.accessToken):void 0}))}",
        "getAccessToken(){return o(this,void 0,void 0,(function*(){var e;/*agentcli-hot-auth*/const t=yield this.readAuthData();return(null==t?void 0:t.accessToken)?(this.cachedAccessToken=t.accessToken,this.cachedRefreshToken=null!==(e=t.refreshToken)&&void 0!==e?e:null,t.accessToken):(this.cachedAccessToken=null,void 0)}))}",
    ),
    (
        "getRefreshToken(){return o(this,void 0,void 0,(function*(){var e;if(this.cachedRefreshToken)return this.cachedRefreshToken;const t=yield this.readAuthData();return(null==t?void 0:t.refreshToken)?(this.cachedAccessToken=null!==(e=t.accessToken)&&void 0!==e?e:null,this.cachedRefreshToken=t.refreshToken,t.refreshToken):void 0}))}",
        "getRefreshToken(){return o(this,void 0,void 0,(function*(){var e;/*agentcli-hot-auth*/const t=yield this.readAuthData();return(null==t?void 0:t.refreshToken)?(this.cachedAccessToken=null!==(e=t.accessToken)&&void 0!==e?e:null,this.cachedRefreshToken=t.refreshToken,t.refreshToken):(this.cachedRefreshToken=null,void 0)}))}",
    ),
    (
        "getApiKey(){return o(this,void 0,void 0,(function*(){if(this.cachedApiKey)return this.cachedApiKey;const e=yield this.readAuthData();return(null==e?void 0:e.apiKey)?(this.cachedApiKey=e.apiKey,e.apiKey):void 0}))}",
        "getApiKey(){return o(this,void 0,void 0,(function*(){/*agentcli-hot-auth*/const e=yield this.readAuthData();return(null==e?void 0:e.apiKey)?(this.cachedApiKey=e.apiKey,e.apiKey):(this.cachedApiKey=null,void 0)}))}",
    ),
    (
        "getAllCredentials(){return o(this,void 0,void 0,(function*(){if(null!==this.cachedAccessToken&&null!==this.cachedRefreshToken)return{accessToken:this.cachedAccessToken||void 0,refreshToken:this.cachedRefreshToken||void 0,apiKey:this.cachedApiKey||void 0};const e=yield this.readAuthData();return e?(this.cachedAccessToken=e.accessToken||null,this.cachedRefreshToken=e.refreshToken||null,this.cachedApiKey=e.apiKey||null,{accessToken:e.accessToken||void 0,refreshToken:e.refreshToken||void 0,apiKey:e.apiKey||void 0}):{accessToken:void 0,refreshToken:void 0,apiKey:void 0}}))}",
        "getAllCredentials(){return o(this,void 0,void 0,(function*(){/*agentcli-hot-auth*/const e=yield this.readAuthData();return e?(this.cachedAccessToken=e.accessToken||null,this.cachedRefreshToken=e.refreshToken||null,this.cachedApiKey=e.apiKey||null,{accessToken:e.accessToken||void 0,refreshToken:e.refreshToken||void 0,apiKey:e.apiKey||void 0}):(this.cachedAccessToken=null,this.cachedRefreshToken=null,this.cachedApiKey=null,{accessToken:void 0,refreshToken:void 0,apiKey:void 0})}))}",
    ),
    # secret/keychain store：去掉内存短路
    (
        "getAccessToken(){return c(this,void 0,void 0,(function*(){if(this.cachedAccessToken)return this.cachedAccessToken;const e=yield this.getSecret(this.accessTokenService);return e?(this.cachedAccessToken=e,e):void 0}))}",
        "getAccessToken(){return c(this,void 0,void 0,(function*(){/*agentcli-hot-auth*/const e=yield this.getSecret(this.accessTokenService);return e?(this.cachedAccessToken=e,e):(this.cachedAccessToken=null,void 0)}))}",
    ),
    (
        "getRefreshToken(){return c(this,void 0,void 0,(function*(){if(this.cachedRefreshToken)return this.cachedRefreshToken;const e=yield this.getSecret(this.refreshTokenService);return e?(this.cachedRefreshToken=e,e):void 0}))}",
        "getRefreshToken(){return c(this,void 0,void 0,(function*(){/*agentcli-hot-auth*/const e=yield this.getSecret(this.refreshTokenService);return e?(this.cachedRefreshToken=e,e):(this.cachedRefreshToken=null,void 0)}))}",
    ),
    (
        "getApiKey(){return c(this,void 0,void 0,(function*(){if(this.cachedApiKey)return this.cachedApiKey;const e=yield this.getSecret(this.apiKeyService);return e?(this.cachedApiKey=e,e):void 0}))}",
        "getApiKey(){return c(this,void 0,void 0,(function*(){/*agentcli-hot-auth*/const e=yield this.getSecret(this.apiKeyService);return e?(this.cachedApiKey=e,e):(this.cachedApiKey=null,void 0)}))}",
    ),
    (
        "getAllCredentials(){return c(this,void 0,void 0,(function*(){if(null!==this.cachedAccessToken&&null!==this.cachedRefreshToken)return{accessToken:this.cachedAccessToken||void 0,refreshToken:this.cachedRefreshToken||void 0,apiKey:this.cachedApiKey||void 0};const[e,t,n]=yield Promise.all([null!==this.cachedAccessToken?Promise.resolve(this.cachedAccessToken||void 0):this.getSecret(this.accessTokenService),null!==this.cachedRefreshToken?Promise.resolve(this.cachedRefreshToken||void 0):this.getSecret(this.refreshTokenService),null!==this.cachedApiKey?Promise.resolve(this.cachedApiKey||void 0):this.getSecret(this.apiKeyService)]);return this.cachedAccessToken=e||null,this.cachedRefreshToken=t||null,this.cachedApiKey=n||null,{accessToken:e,refreshToken:t,apiKey:n}}))}",
        "getAllCredentials(){return c(this,void 0,void 0,(function*(){/*agentcli-hot-auth*/const[e,t,n]=yield Promise.all([this.getSecret(this.accessTokenService),this.getSecret(this.refreshTokenService),this.getSecret(this.apiKeyService)]);return this.cachedAccessToken=e||null,this.cachedRefreshToken=t||null,this.cachedApiKey=n||null,{accessToken:e,refreshToken:t,apiKey:n}}))}",
    ),
    # memory AuthStorage：禁止返回进程内字段（工厂已强制 file；此为兜底）
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
    # 核弹：每次设 Bearer 前同步读盘覆盖 l，并写入 agentcli-last-bearer.json 供对照
    (
        'l=yield(0,B.uX)(e,a);null!=l&&s.header.set("authorization",`Bearer ${l}`);',
        'l=yield(0,B.uX)(e,a);'
        + _DISK_BEARER_OVERRIDE
        + 'null!=l&&s.header.set("authorization",`Bearer ${l}`);',
    ),
    (
        '}(e,a);null!=l&&s.header.set("authorization",`Bearer ${l}`);',
        '}(e,a);'
        + _DISK_BEARER_OVERRIDE
        + 'null!=l&&s.header.set("authorization",`Bearer ${l}`);',
    ),
)

# cursor-agent.ps1：关掉 Node compile cache，保证 index.js 热补丁字节码不被旧缓存顶替
_COMPILE_CACHE_OLD = (
    "## Enable Node.js compile cache for faster CLI startup (requires Node.js >= 22.1.0)\n"
    "## Cache is automatically invalidated when source files change\n"
    "if (-not $env:NODE_COMPILE_CACHE) {\n"
    '    $env:NODE_COMPILE_CACHE = "$env:LOCALAPPDATA\\cursor-compile-cache"\n'
    "}"
)
_COMPILE_CACHE_NEW = (
    "## agentcli-hot-auth: disable NODE_COMPILE_CACHE so index.js patches always load\n"
    "Remove-Item Env:NODE_COMPILE_CACHE -ErrorAction SilentlyContinue\n"
)


def apply_hot_auth_replacements(content: str) -> tuple[str, int]:
    """对原始/已部分打补丁的 index.js 文本应用全部 hot-auth 替换。

    Returns:
        (modified_text, hit_count) — hit_count 含「本次替换」与「已是目标形态」。
    """
    modified = content
    hits = 0
    for old, new in _REPLACEMENTS:
        if old in modified:
            modified = modified.replace(old, new, 1)
            hits += 1
        elif new in modified:
            hits += 1
    return modified, hits


def clear_node_compile_cache() -> Optional[Path]:
    """删除 %LOCALAPPDATA%\\cursor-compile-cache，迫使下次冷加载 index.js。"""
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    cache = Path(local) / "cursor-compile-cache"
    if cache.is_dir():
        shutil.rmtree(cache, ignore_errors=True)
        return cache
    return None

_BOOT_BLOCK = f"""{BOOT_MARKER}
REM Start sc auto via helper script (avoids cmd quoting bugs); parent=cmd.exe
if exist "%~dp0sc-autoboot.ps1" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0sc-autoboot.ps1"
"""

_SC_AUTOBOOT_PS1 = r"""$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$sc = Join-Path $root "sc.cmd"
if (-not (Test-Path -LiteralPath $sc)) { exit 0 }
# 已有新鲜 leader 心跳则不重复拉起，避免 agent 每次启动叠 trop 多实例抢写 status。
$inst = Join-Path $env:USERPROFILE ".cursor\sc_instances.json"
if (Test-Path -LiteralPath $inst) {
  try {
    $doc = Get-Content -LiteralPath $inst -Raw -Encoding UTF8 | ConvertFrom-Json
    $lid = $doc.leader_id
    if ($lid) {
      $info = $doc.instances.$lid
      if ($null -ne $info -and $null -ne $info.heartbeat_at) {
        $hb = [double]$info.heartbeat_at
        $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        # Python time.time() 是本地 epoch 秒；与 UTC epoch 相同
        if (($now - $hb) -lt 10) { exit 0 }
      }
    }
  } catch {}
}
# 不绑 --parent：cmd/powershell 短命父进程会导致 auto 被误杀，statusLine 长期 STALE。
# 多实例靠 sc_instances 心跳选举 leader；退出用 sc auto stop 或进程结束。
$argv = @("auto", "--fg")
Start-Process -FilePath $sc -ArgumentList $argv -WindowStyle Hidden | Out-Null
"""

# Ctrl+C 时避免 "Terminate batch job (Y/N)?"：endlocal 后脱离 batch 再等 PowerShell
_AG_CMD = r"""@echo off
setlocal EnableExtensions
set "CURSOR_INVOKED_AS=%~nx0"
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "_PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
set "_SCRIPT=%SCRIPT_DIR%\cursor-agent.ps1"
REM agentcli-no-terminate-prompt
endlocal & set "CURSOR_INVOKED_AS=%~nx0" & "%_PS%" -NoProfile -ExecutionPolicy Bypass -File "%_SCRIPT%" %*
"""

_CURSOR_AGENT_CMD_TAIL = r"""set "CURSOR_INVOKED_AS=%~nx0"
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "_PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
set "_SCRIPT=%SCRIPT_DIR%\cursor-agent.ps1"
REM agentcli-no-terminate-prompt
endlocal & set "CURSOR_INVOKED_AS=%~nx0" & "%_PS%" -NoProfile -ExecutionPolicy Bypass -File "%_SCRIPT%" %*
"""

_SC_CMD = r"""@echo off
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set "SCRIPT_DIR=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%sc.ps1" %*
"""

# statusLine 每 1s 调一次：直调极速模块，禁止套 PowerShell / 全量 sc.cli
_SC_STATUSLINE_CMD = r"""@echo off
setlocal
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
if defined AGENTCLI_PATCHS_SRC (set "PYTHONPATH=%AGENTCLI_PATCHS_SRC%") else (set "PYTHONPATH=X:\Project\Public\AgentCLI-Patchs\src")
if defined AGENTCLI_PYTHON (set "PY=%AGENTCLI_PYTHON%") else (set "PY=python")
"%PY%" -X utf8 -m sc.statusline_fast
"""

# client.py 旁默认配置路径（复制到 %APPDATA%\Cursor\config.json）
_CLIENT_CONFIG_CANDIDATES = (
    Path(r"X:\Project\Common\Common\config.json"),
    Path(r"X:\Project\Common\config.json"),
)


def _sc_ps1(src_dir: Path) -> str:
    src = str(src_dir).replace("'", "''")
    return f"""param([Parameter(ValueFromRemainingArguments=$true)]$ArgsRest)
$ErrorActionPreference = "Stop"
try {{ chcp 65001 | Out-Null }} catch {{}}
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONPATH = if ($env:AGENTCLI_PATCHS_SRC) {{ $env:AGENTCLI_PATCHS_SRC }} else {{ '{src}' }}
$py = if ($env:AGENTCLI_PYTHON) {{ $env:AGENTCLI_PYTHON }} else {{ 'python' }}
& $py -X utf8 -m sc @ArgsRest
exit $LASTEXITCODE
"""


def find_client_config() -> Optional[Path]:
    for p in _CLIENT_CONFIG_CANDIDATES:
        if p.is_file():
            return p
    return None


def ensure_sc_config_from_client(*, force: bool = False) -> Optional[Path]:
    """把 client.py 同目录 config.json 复制到与 auth.json 同级。"""
    src = find_client_config()
    if src is None:
        return None
    dst = config_json_path()
    if dst.exists() and not force:
        # 已有配置：若 api_keys 为空则仍覆盖
        try:
            cur = json.loads(dst.read_text(encoding="utf-8"))
            if cur.get("api_keys"):
                return dst
        except Exception:
            pass
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    logger.info("Copied SC config {} → {}", src, dst)
    return dst


class CursorAgentPatch(PatchBase):
    """Hot-reload auth + auto-boot sc auto + /sc slash + statusline。"""

    @property
    def metadata(self) -> PatchMetadata:
        return PatchMetadata(
            name="cursor-agent",
            display_name="Cursor Agent 热更新与自动换号",
            description=(
                "AuthStorage/keychain/ephemeral 全部强制读盘；禁用 NODE_COMPILE_CACHE；"
                "启动 agent 时自动后台 sc auto；注入 /sc pull|usage；statusline 定时刷新。"
            ),
            version="2.3.1",
            author="nichengfuben",
            target_files=(
                "index.js",
                "*.index.js",
            ),
            tags=("cursor-agent", "auth", "hot-reload", "sc", "auto", "statusline", "slash"),
            reversible=True,
        )

    def validate(self, bundle_dir: Path) -> list[str]:
        """校验 cursor-agent 安装目录（不依赖 Qoder bundle_dir）。"""
        issues: list[str] = []
        target = self._resolve_bundle(bundle_dir)
        if target is None:
            issues.append("未找到 %LOCALAPPDATA%\\cursor-agent\\versions\\*\\index.js")
            return issues
        index = self._index_js(target)
        if not index.exists():
            issues.append(f"Target file does not exist: {index}")
        elif not index.is_file():
            issues.append(f"Target is not a file: {index}")
        root = find_cursor_agent_root()
        if root is None:
            issues.append("未找到 %LOCALAPPDATA%\\cursor-agent")
        return issues

    def _index_js(self, bundle_dir: Path) -> Path:
        return bundle_dir / "index.js"

    def _slash_chunks(self, bundle_dir: Path) -> list[Path]:
        hits: list[Path] = []
        for path in bundle_dir.glob("*.index.js"):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if SLASH_MARKER in text or 'ue.push({id:"sc"' in text:
                hits.append(path)
        return hits

    def _resolve_bundle(self, bundle_dir: Optional[Path] = None) -> Optional[Path]:
        if bundle_dir is not None and (bundle_dir / "index.js").exists():
            return bundle_dir
        return find_cursor_agent_bundle()

    def check(self, bundle_dir: Path) -> PatchStatus:
        target = self._resolve_bundle(bundle_dir)
        if target is None:
            return PatchStatus.UNKNOWN
        index = self._index_js(target)
        if not index.exists():
            return PatchStatus.UNKNOWN
        text = index.read_text(encoding="utf-8", errors="ignore")
        root = find_cursor_agent_root()
        sc_ok = bool(root and (root / "sc.cmd").exists() and (root / "sc-statusline.cmd").exists())
        hot_ok = MARKER in text and EPHEMERAL_NULL_MARKER in text and DISK_MARKER in text
        interval_ok = any(
            STATUS_INTERVAL_MARKER in p.read_text(encoding="utf-8", errors="ignore")
            for p in target.glob("*.index.js")
            if p.is_file()
        )
        footer_ok = any(
            FOOTER_KEEP_MARKER in p.read_text(encoding="utf-8", errors="ignore")
            for p in target.glob("*.index.js")
            if p.is_file()
        )
        boot_ok = False
        if root is not None:
            boot_cmd = root / "cursor-agent.cmd"
            if boot_cmd.exists():
                boot_ok = BOOT_MARKER in boot_cmd.read_text(encoding="utf-8", errors="ignore")
        slash_ok = len(self._slash_chunks(target)) > 0
        if hot_ok and sc_ok and boot_ok and slash_ok and interval_ok and footer_ok:
            return PatchStatus.APPLIED
        if hot_ok or sc_ok or boot_ok or slash_ok or interval_ok or footer_ok:
            return PatchStatus.PARTIAL
        return PatchStatus.NOT_APPLIED

    def _patch_hot_auth(self, index: Path, dry_run: bool) -> tuple[int, Optional[Path], Optional[Path]]:
        content = index.read_text(encoding="utf-8", errors="ignore")
        modified, hits = apply_hot_auth_replacements(content)
        if dry_run or modified == content:
            return hits, None, None
        self._assert_js_syntax(index, modified)
        bak = index.with_suffix(index.suffix + f".bak.{time.strftime('%Y%m%d%H%M%S')}")
        bak.write_text(content, encoding="utf-8")
        index.write_text(modified, encoding="utf-8")
        return hits, index, bak

    def _patch_compile_cache_ps1(
        self, root: Path, dry_run: bool
    ) -> tuple[int, list[Path], list[Path]]:
        """根目录与当前 version 的 cursor-agent.ps1：禁用 NODE_COMPILE_CACHE。"""
        files: list[Path] = []
        backups: list[Path] = []
        hits = 0
        candidates = [root / "cursor-agent.ps1"]
        bundle = find_cursor_agent_bundle()
        if bundle is not None:
            candidates.append(bundle / "cursor-agent.ps1")
        seen: set[Path] = set()
        for path in candidates:
            try:
                resolved = path.resolve()
            except OSError:
                resolved = path
            if resolved in seen or not path.is_file():
                continue
            seen.add(resolved)
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if "agentcli-hot-auth: disable NODE_COMPILE_CACHE" in text:
                hits += 1
                continue
            if _COMPILE_CACHE_OLD not in text:
                continue
            hits += 1
            if dry_run:
                continue
            bak = path.with_suffix(path.suffix + f".bak.{time.strftime('%Y%m%d%H%M%S')}")
            bak.write_text(text, encoding="utf-8")
            backups.append(bak)
            path.write_text(
                text.replace(_COMPILE_CACHE_OLD, _COMPILE_CACHE_NEW, 1),
                encoding="utf-8",
                newline="\n",
            )
            files.append(path)
            logger.info("Disabled NODE_COMPILE_CACHE in {}", path)
        return hits, files, backups

    def _patch_statusline_interval(
        self, bundle_dir: Path, dry_run: bool
    ) -> tuple[int, list[Path], list[Path]]:
        """把 use-status-line 的 debounce 改成按 updateIntervalMs 的 setInterval。"""
        files: list[Path] = []
        backups: list[Path] = []
        hits = 0
        for chunk in bundle_dir.glob("*.index.js"):
            try:
                text = chunk.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if STATUS_INTERVAL_MARKER in text:
                hits += 1
                continue
            if _STATUS_INTERVAL_OLD not in text:
                continue
            if dry_run:
                hits += 1
                continue
            bak = chunk.with_suffix(chunk.suffix + f".bak.{time.strftime('%Y%m%d%H%M%S')}")
            bak.write_text(text, encoding="utf-8")
            chunk.write_text(
                text.replace(_STATUS_INTERVAL_OLD, _STATUS_INTERVAL_NEW, 1),
                encoding="utf-8",
            )
            files.append(chunk)
            backups.append(bak)
            hits += 1
            logger.info("Patched statusLine interval in {}", chunk.name)
        return hits, files, backups

    def _strip_statusline_interval(
        self, bundle_dir: Path, dry_run: bool
    ) -> tuple[int, list[Path]]:
        files: list[Path] = []
        hits = 0
        for chunk in bundle_dir.glob("*.index.js"):
            try:
                text = chunk.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if _STATUS_INTERVAL_NEW not in text and STATUS_INTERVAL_MARKER not in text:
                continue
            if dry_run:
                hits += 1
                continue
            restored = text.replace(_STATUS_INTERVAL_NEW, _STATUS_INTERVAL_OLD, 1)
            if restored == text:
                continue
            chunk.write_text(restored, encoding="utf-8")
            files.append(chunk)
            hits += 1
        return hits, files

    def _patch_footer_keep(
        self, bundle_dir: Path, dry_run: bool
    ) -> tuple[int, list[Path], list[Path]]:
        """保留原生页脚，SC statusLine 只追加一行。"""
        files: list[Path] = []
        backups: list[Path] = []
        hits = 0
        for chunk in bundle_dir.glob("*.index.js"):
            try:
                text = chunk.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if FOOTER_KEEP_MARKER in text:
                hits += 1
                continue
            if _FOOTER_KEEP_OLD not in text:
                continue
            if dry_run:
                hits += 1
                continue
            bak = chunk.with_suffix(chunk.suffix + f".bak.{time.strftime('%Y%m%d%H%M%S')}")
            bak.write_text(text, encoding="utf-8")
            chunk.write_text(
                text.replace(_FOOTER_KEEP_OLD, _FOOTER_KEEP_NEW, 1),
                encoding="utf-8",
            )
            files.append(chunk)
            backups.append(bak)
            hits += 1
            logger.info("Patched prompt-footer keep-native in {}", chunk.name)
        return hits, files, backups

    def _strip_footer_keep(
        self, bundle_dir: Path, dry_run: bool
    ) -> tuple[int, list[Path]]:
        files: list[Path] = []
        hits = 0
        for chunk in bundle_dir.glob("*.index.js"):
            try:
                text = chunk.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if _FOOTER_KEEP_NEW not in text and FOOTER_KEEP_MARKER not in text:
                continue
            if dry_run:
                hits += 1
                continue
            restored = text.replace(_FOOTER_KEEP_NEW, _FOOTER_KEEP_OLD, 1)
            if restored == text:
                continue
            chunk.write_text(restored, encoding="utf-8")
            files.append(chunk)
            hits += 1
        return hits, files

    def _inject_slash(self, bundle_dir: Path, dry_run: bool) -> tuple[int, list[Path], list[Path]]:
        """注入 / 更新 /sc slash（仅 pull|usage；异步 spawn）。"""
        files: list[Path] = []
        backups: list[Path] = []
        hits = 0
        for chunk in bundle_dir.glob("*.index.js"):
            try:
                text = chunk.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if _SLASH_ANCHOR not in text and 'ue.push({id:"sc"' not in text:
                continue
            # 已有旧注入：先剥掉再写入新版
            working = text
            if SLASH_MARKER in working or 'ue.push({id:"sc"' in working:
                start = working.find('ue.push({id:"sc"')
                end = working.find('ue.push({id:"plugin"', start) if start >= 0 else -1
                if start >= 0 and end > start:
                    working = working[:start] + working[end:]
            if _SLASH_ANCHOR not in working:
                continue
            if _SLASH_INJECT in working:
                hits += 1
                continue
            hits += 1
            if dry_run:
                continue
            new_text = working.replace(_SLASH_ANCHOR, _SLASH_INJECT, 1)
            self._assert_js_syntax(chunk, new_text)
            bak = chunk.with_suffix(chunk.suffix + f".bak.{time.strftime('%Y%m%d%H%M%S')}")
            bak.write_text(text, encoding="utf-8")
            backups.append(bak)
            chunk.write_text(new_text, encoding="utf-8")
            files.append(chunk)
            logger.info("Injected /sc slash (pull|usage) into {}", chunk)
        return hits, files, backups

    def _strip_slash(self, bundle_dir: Path, dry_run: bool) -> tuple[int, list[Path], list[Path]]:
        """移除历史 /sc slash 注入（rollback）。"""
        files: list[Path] = []
        backups: list[Path] = []
        hits = 0
        for chunk in self._slash_chunks(bundle_dir):
            text = chunk.read_text(encoding="utf-8", errors="ignore")
            if SLASH_MARKER not in text and 'ue.push({id:"sc"' not in text:
                continue
            start = text.find('ue.push({id:"sc"')
            end = text.find('ue.push({id:"plugin"', start) if start >= 0 else -1
            if start < 0 or end <= start:
                continue
            hits += 1
            if dry_run:
                continue
            new_text = text[:start] + text[end:]
            self._assert_js_syntax(chunk, new_text)
            bak = chunk.with_suffix(chunk.suffix + f".bak.{time.strftime('%Y%m%d%H%M%S')}")
            bak.write_text(text, encoding="utf-8")
            backups.append(bak)
            chunk.write_text(new_text, encoding="utf-8")
            files.append(chunk)
            logger.info("Removed /sc slash from {}", chunk)
        return hits, files, backups

    def _assert_js_syntax(self, path: Path, source: str) -> None:
        import subprocess
        import tempfile

        node = find_cursor_agent_bundle()
        node_exe = (node / "node.exe") if node and (node / "node.exe").exists() else Path("node")
        with tempfile.NamedTemporaryFile(
            "w", suffix=".js", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(source)
            tmp_path = tmp.name
        try:
            proc = subprocess.run(
                [str(node_exe), "--check", tmp_path],
                capture_output=True,
                text=True,
                timeout=60,
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()
            raise RuntimeError(f"JS syntax check failed on {path.name}: {err}")

    def _patch_boot_cmd(self, root: Path, dry_run: bool) -> tuple[bool, Optional[Path], Optional[Path]]:
        cmd = root / "cursor-agent.cmd"
        if not cmd.exists():
            return False, None, None
        text = cmd.read_text(encoding="utf-8", errors="ignore")
        boot = _BOOT_BLOCK if _BOOT_BLOCK.endswith("\n") else _BOOT_BLOCK + "\n"
        # 完整重写：boot + no-terminate 启动尾（避免 Terminate batch job）
        new_text = (
            "@echo off\r\n"
            "setlocal EnableExtensions\r\n"
            "\r\n"
            + boot.replace("\n", "\r\n")
            + "\r\n"
            + _CURSOR_AGENT_CMD_TAIL.replace("\n", "\r\n")
        )
        if text.replace("\r\n", "\n").strip() == new_text.replace("\r\n", "\n").strip():
            return True, None, None
        if dry_run:
            return True, None, None
        bak = cmd.with_suffix(cmd.suffix + f".bak.{time.strftime('%Y%m%d%H%M%S')}")
        bak.write_text(text, encoding="utf-8")
        cmd.write_text(new_text, encoding="utf-8", newline="")
        logger.info("Patched cursor-agent.cmd boot+no-terminate → {}", cmd)
        return True, cmd, bak

    def _patch_launchers(self, root: Path, dry_run: bool) -> tuple[bool, list[Path], list[Path]]:
        """写入 ag.cmd / agent.cmd（no-terminate），与 cursor-agent.cmd 对齐。"""
        files: list[Path] = []
        backups: list[Path] = []
        wanted = _AG_CMD.replace("\n", "\r\n")
        changed = False
        for name in ("ag.cmd", "agent.cmd"):
            path = root / name
            if not path.exists():
                continue
            old = path.read_text(encoding="utf-8", errors="ignore")
            if old.replace("\r\n", "\n").strip() == _AG_CMD.strip():
                continue
            changed = True
            if dry_run:
                continue
            bak = path.with_suffix(path.suffix + f".bak.{time.strftime('%Y%m%d%H%M%S')}")
            bak.write_text(old, encoding="utf-8")
            backups.append(bak)
            path.write_text(wanted, encoding="utf-8", newline="")
            files.append(path)
            logger.info("Patched {} no-terminate", name)
        return changed or bool(files), files, backups

    def apply(self, bundle_dir: Path, dry_run: bool = False) -> PatchResult:
        start = time.monotonic()
        target = self._resolve_bundle(bundle_dir)
        if target is None:
            return PatchResult(
                status=PatchStatus.FAILED,
                message="未找到 cursor-agent version 目录（index.js）",
                patch_name=self.metadata.name,
                duration_ms=int((time.monotonic() - start) * 1000),
                error="bundle not found",
            )
        index = self._index_js(target)
        content = index.read_text(encoding="utf-8", errors="ignore")
        hot_hits, _, _ = self._patch_hot_auth(index, dry_run=True)
        root = find_cursor_agent_root()
        interval_hits, _, _ = self._patch_statusline_interval(target, dry_run=True)
        footer_hits, _, _ = self._patch_footer_keep(target, dry_run=True)
        ps1_hits, _, _ = (
            self._patch_compile_cache_ps1(root, dry_run=True) if root else (0, [], [])
        )

        if dry_run:
            return PatchResult(
                status=PatchStatus.APPLIED if hot_hits >= 1 or MARKER in content else PatchStatus.FAILED,
                message=(
                    f"[dry-run] hot-auth hits={hot_hits}, status-interval={interval_hits}, "
                    f"footer-keep={footer_hits}, compile-cache-ps1={ps1_hits}, "
                    f"would install sc/auto-boot at {root}"
                ),
                patch_name=self.metadata.name,
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        if hot_hits == 0 and MARKER not in content:
            return PatchResult(
                status=PatchStatus.FAILED,
                message="未匹配到 AuthStorage 缓存片段（cursor-agent 版本可能已变）",
                patch_name=self.metadata.name,
                duration_ms=int((time.monotonic() - start) * 1000),
                error="pattern miss",
            )

        files: list[Path] = []
        backups: list[Path] = []
        hot_hits, hot_file, hot_bak = self._patch_hot_auth(index, dry_run=False)
        if hot_file:
            files.append(hot_file)
        if hot_bak:
            backups.append(hot_bak)
            logger.info("Patched hot-auth in {}", index)

        if root is not None:
            _, ps1_files, ps1_baks = self._patch_compile_cache_ps1(root, dry_run=False)
            files.extend(ps1_files)
            backups.extend(ps1_baks)
        cleared = clear_node_compile_cache()
        if cleared:
            logger.info("Cleared NODE_COMPILE_CACHE dir {}", cleared)

        stripped, slash_files, slash_baks = self._inject_slash(target, dry_run=False)
        files.extend(slash_files)
        backups.extend(slash_baks)

        iv_hits, iv_files, iv_baks = self._patch_statusline_interval(target, dry_run=False)
        files.extend(iv_files)
        backups.extend(iv_baks)

        ft_hits, ft_files, ft_baks = self._patch_footer_keep(target, dry_run=False)
        files.extend(ft_files)
        backups.extend(ft_baks)

        # 勿 force：避免每次 apply 把 Common 的 switch_threshold=80 盖掉本地 95%
        cfg_copied = ensure_sc_config_from_client(force=False)
        if cfg_copied:
            files.append(cfg_copied)

        if root is not None:
            src = get_project_root() / "src"
            cmd = root / "sc.cmd"
            ps1 = root / "sc.ps1"
            sl_cmd = root / "sc-statusline.cmd"
            boot_ps1 = root / "sc-autoboot.ps1"
            cmd.write_text(_SC_CMD, encoding="utf-8")
            ps1.write_text(_sc_ps1(src), encoding="utf-8")
            sl_cmd.write_text(_SC_STATUSLINE_CMD, encoding="utf-8")
            boot_ps1.write_text(_SC_AUTOBOOT_PS1, encoding="utf-8")
            files.extend([cmd, ps1, sl_cmd, boot_ps1])
            boot_ok, boot_file, boot_bak = self._patch_boot_cmd(root, dry_run=False)
            if boot_file:
                files.append(boot_file)
            if boot_bak:
                backups.append(boot_bak)
            ag_ok, ag_files, ag_baks = self._patch_launchers(root, dry_run=False)
            files.extend(ag_files)
            backups.extend(ag_baks)
            cfg_path = merge_status_line(str(sl_cmd.resolve()))
            files.append(cfg_path)
            logger.info("Wired statusLine → {}", cfg_path)
        else:
            boot_ok = False
            ag_ok = False

        return PatchResult(
            status=PatchStatus.APPLIED,
            message=(
                f"hot-auth(v2 ephemeral-off) + auto-boot + /sc + statusline 已应用 "
                f"(hot={hot_hits}, slash={stripped}, interval={iv_hits}, footer={ft_hits}, "
                f"boot={boot_ok}, "
                f"launchers={ag_ok}, config={cfg_copied}, root={root})"
            ),
            patch_name=self.metadata.name,
            files_modified=files,
            backups_created=backups,
            duration_ms=int((time.monotonic() - start) * 1000),
        )

    def rollback(self, bundle_dir: Path, dry_run: bool = False) -> PatchResult:
        start = time.monotonic()
        target = self._resolve_bundle(bundle_dir)
        if target is None:
            return PatchResult(
                status=PatchStatus.FAILED,
                message="未找到 cursor-agent bundle",
                patch_name=self.metadata.name,
                duration_ms=int((time.monotonic() - start) * 1000),
                error="missing",
            )
        index = self._index_js(target)
        content = index.read_text(encoding="utf-8", errors="ignore")
        restored = content
        for old, new in _REPLACEMENTS:
            if new in restored:
                restored = restored.replace(new, old, 1)
        files: list[Path] = []
        if dry_run:
            return PatchResult(
                status=PatchStatus.NOT_APPLIED,
                message="[dry-run] would rollback hot-auth, footer-keep, boot, slash, sc launchers",
                patch_name=self.metadata.name,
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        if restored != content:
            index.write_text(restored, encoding="utf-8")
            files.append(index)
        _, slash_files, _ = self._strip_slash(target, dry_run=False)
        files.extend(slash_files)
        _, iv_files = self._strip_statusline_interval(target, dry_run=False)
        files.extend(iv_files)
        _, ft_files = self._strip_footer_keep(target, dry_run=False)
        files.extend(ft_files)
        root = find_cursor_agent_root()
        if root:
            cmd = root / "cursor-agent.cmd"
            if cmd.exists():
                text = cmd.read_text(encoding="utf-8", errors="ignore")
                if BOOT_MARKER in text:
                    # 去掉 boot 块：从 marker 到下一空行/原内容
                    lines = text.splitlines(keepends=True)
                    out: list[str] = []
                    skip = False
                    for line in lines:
                        if BOOT_MARKER in line:
                            skip = True
                            continue
                        if skip:
                            if line.strip() == "" and out and not out[-1].strip().startswith("REM"):
                                skip = False
                            if skip and (
                                line.strip().startswith("REM ")
                                or line.strip().startswith("if exist")
                                or line.strip().startswith("start ")
                                or line.strip() == ")"
                                or line.strip() == ""
                            ):
                                if line.strip() == ")" or (
                                    line.strip() == "" and "start" in "".join(out[-5:])
                                ):
                                    if line.strip() == ")":
                                        skip = False
                                    continue
                                continue
                            skip = False
                        out.append(line)
                    cmd.write_text("".join(out), encoding="utf-8")
                    files.append(cmd)
            for name in ("sc.cmd", "sc.ps1", "sc-statusline.cmd", "sc-autoboot.ps1"):
                p = root / name
                if p.exists():
                    p.unlink()
                    files.append(p)
        return PatchResult(
            status=PatchStatus.NOT_APPLIED,
            message="已回滚 hot-auth、status-interval、footer-keep、auto-boot、slash，并移除 sc 启动器",
            patch_name=self.metadata.name,
            files_modified=files,
            duration_ms=int((time.monotonic() - start) * 1000),
        )
