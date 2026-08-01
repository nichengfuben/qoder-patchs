from __future__ import annotations

"""UI chunk patch patterns (statusline/footer/slash)."""

STATUS_INTERVAL_MARKER = "/*agentcli-status-interval*/"
FOOTER_KEEP_MARKER = "/*agentcli-footer-keep*/"
SLASH_MARKER = "/*agentcli-sc-slash*/"

# use-status-line.ts：上游把 updateIntervalMs 当成 debounce，不是定时器。
# 空闲时 updateSignal 不变 → statusLine 不刷新 → 时钟卡住。
# 补 setInterval；必须直调 S（不要走 debounced C），否则 tick 会被 debounce 吞掉。
_STATUS_INTERVAL_OLD = (
    "return(0,l.useEffect)((()=>{var e;return b?(C(E.payload),()=>{var e;"
    "C.cancel(),null===(e=m.current)||void 0===e||e.abort()}):(C.cancel(),"
    "null===(e=m.current)||void 0===e||e.abort(),m.current=null,v.current=null,"
    "void g(null))}),[E,C,b]),{text:p,padding:y}}"
)
# 旧版补丁：setInterval→C（仍经 debounce），升级时替换
_STATUS_INTERVAL_V1 = (
    "return(0,l.useEffect)((()=>{var e;"
    + STATUS_INTERVAL_MARKER
    + "if(!b)return C.cancel(),null===(e=m.current)||void 0===e||e.abort(),"
    "m.current=null,v.current=null,void g(null);"
    "C(E.payload);const t=setInterval((()=>C(E.payload)),w);"
    "return()=>{clearInterval(t),C.cancel(),null===(e=m.current)||void 0===e||e.abort()}"
    "}),[E,C,b,w]),{text:p,padding:y}}"
)
# v2：直调 S 但 deps 含 E → updateSignal 一变就 tearDown interval（跑久必挂）
_STATUS_INTERVAL_V2 = (
    "return(0,l.useEffect)((()=>{var e;"
    + STATUS_INTERVAL_MARKER
    + "if(!b)return C.cancel(),null===(e=m.current)||void 0===e||e.abort(),"
    "m.current=null,v.current=null,void g(null);"
    "const r=()=>{var a;null===(a=m.current)||void 0===a||a.abort();"
    "const n=new AbortController;m.current=n,S(E.payload,n.signal)};"
    "r();const t=setInterval(r,w);"
    "return()=>{clearInterval(t),C.cancel(),null===(e=m.current)||void 0===e||e.abort()}"
    "}),[E,C,b,w,S]),{text:p,padding:y}}"
)
# v3：payload ref + 稳定 deps，interval 不被 updateSignal 打断
_STATUS_INTERVAL_REF = "const _scPl=(0,l.useRef)(t);_scPl.current=t;"
_STATUS_INTERVAL_NEW = (
    "return(0,l.useEffect)((()=>{var e;"
    + STATUS_INTERVAL_MARKER
    + "if(!b)return C.cancel(),null===(e=m.current)||void 0===e||e.abort(),"
    "m.current=null,v.current=null,void g(null);"
    "const r=()=>{var a;null===(a=m.current)||void 0===a||a.abort();"
    "const n=new AbortController;m.current=n,S(_scPl.current,n.signal)};"
    "r();const t=setInterval(r,w);"
    "return()=>{clearInterval(t),C.cancel(),null===(e=m.current)||void 0===e||e.abort()}"
    "}),[b,w,S,x]),{text:p,padding:y}}"
)
_STATUS_INTERVAL_BEFORE_EFFECT = (
    "E=(0,l.useMemo)((()=>({payload:t,updateSignal:s,commandKey:x})),[t,s,x]);return(0,l.useEffect)"
)
_STATUS_INTERVAL_BEFORE_EFFECT_REF = (
    "E=(0,l.useMemo)((()=>({payload:t,updateSignal:s,commandKey:x})),[t,s,x]);"
    + _STATUS_INTERVAL_REF
    + "return(0,l.useEffect)"
)


def apply_statusline_interval_text(text: str) -> tuple[str, str]:
    """返回 (新文本, 动作标签)；已是 v3 则 ("", "")。"""
    if _STATUS_INTERVAL_NEW in text and _STATUS_INTERVAL_REF in text:
        return "", ""
    if _STATUS_INTERVAL_V2 in text:
        text = text.replace(_STATUS_INTERVAL_V2, _STATUS_INTERVAL_NEW, 1)
        label = "upgrade-v2"
    elif _STATUS_INTERVAL_V1 in text:
        text = text.replace(_STATUS_INTERVAL_V1, _STATUS_INTERVAL_NEW, 1)
        label = "upgrade-v1"
    elif _STATUS_INTERVAL_OLD in text:
        text = text.replace(_STATUS_INTERVAL_OLD, _STATUS_INTERVAL_NEW, 1)
        label = "patch"
    else:
        return "", ""
    if _STATUS_INTERVAL_BEFORE_EFFECT in text and _STATUS_INTERVAL_REF not in text:
        text = text.replace(_STATUS_INTERVAL_BEFORE_EFFECT, _STATUS_INTERVAL_BEFORE_EFFECT_REF, 1)
    return text, label


def restore_statusline_interval_text(text: str) -> str:
    restored = text.replace(_STATUS_INTERVAL_NEW, _STATUS_INTERVAL_OLD, 1)
    if restored == text:
        restored = text.replace(_STATUS_INTERVAL_V2, _STATUS_INTERVAL_OLD, 1)
    if restored == text:
        restored = text.replace(_STATUS_INTERVAL_V1, _STATUS_INTERVAL_OLD, 1)
    if restored != text and _STATUS_INTERVAL_BEFORE_EFFECT_REF in restored:
        restored = restored.replace(
            _STATUS_INTERVAL_BEFORE_EFFECT_REF, _STATUS_INTERVAL_BEFORE_EFFECT, 1
        )
    return restored


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
    'const cp=n("node:child_process"),path=n("node:path"),fs=n("node:fs"),os=n("node:os");'
    'const root="win32"===process.platform'
    '?path.join(process.env.LOCALAPPDATA||"","cursor-agent")'
    ':path.join(os.homedir(),".local","share","cursor-agent");'
    'const scCmd=path.join(root,"win32"===process.platform?"sc.cmd":"sc");'
    'const env=Object.assign({},process.env,{PYTHONUTF8:"1",PYTHONIOENCODING:"utf-8"});'
    "const result=yield new Promise((resolve)=>{let out=\"\",err=\"\",cmd,args,opts;"
    "if(scCmd&&fs.existsSync(scCmd)){cmd=scCmd;args=[sub];opts={env,shell:!0}}"
    'else{cmd=process.env.PATCHER_PYTHON||process.env.AGENTCLI_PYTHON||("win32"===process.platform?"python":"python3");'
    'args=["-m","sc",sub];opts={env,shell:!1}}'
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

# 每次 Authorization 写入前强制读盘；优先 process.getBuiltinModule（webpack 内 require 可能不可用）
# 注意：外层常是 const l=yield...，不能给 l 赋值；写入 _agentcliBearer。
_DISK_BEARER_OVERRIDE = (
    '{/*agentcli-hot-auth-disk*/try{const _fs=(process.getBuiltinModule&&'
    '(process.getBuiltinModule("node:fs")||process.getBuiltinModule("fs")))||'
    'require("node:fs");const _path=(process.getBuiltinModule&&'
    '(process.getBuiltinModule("node:path")||process.getBuiltinModule("path")))||'
    'require("node:path");const _os=(process.getBuiltinModule&&'
    '(process.getBuiltinModule("node:os")||process.getBuiltinModule("os")))||'
    'require("node:os");const _dir="win32"===process.platform?_path.join('
    'process.env.APPDATA||_path.join(_os.homedir(),"AppData","Roaming"),"Cursor")'
    ':_path.join(_os.homedir(),".cursor");const _auth=_path.join(_dir,"auth.json");'
    'const _j=JSON.parse(_fs.readFileSync(_auth,"utf8"));'
    'if(_j&&_j.accessToken)_agentcliBearer=_j.accessToken;'
    'try{const _sub=JSON.parse(Buffer.from(String(_agentcliBearer).split(".")[1],"base64").toString()).sub;'
    'globalThis.__agentcliRunSub=_sub;'
    '_fs.writeFileSync(_path.join(_dir,"agentcli-last-bearer.json"),'
    'JSON.stringify({sub:_sub,ts:Date.now(),pid:process.pid,via:"disk-override"}))}'
    'catch(_e){}}catch(_e){}}'
)

# 已打 disk-override、尚无 __agentcliRunSub 时的升级路径
_DISK_BEARER_OVERRIDE_V1 = (
    '{/*agentcli-hot-auth-disk*/try{const _fs=(process.getBuiltinModule&&'
    '(process.getBuiltinModule("node:fs")||process.getBuiltinModule("fs")))||'
    'require("node:fs");const _path=(process.getBuiltinModule&&'
    '(process.getBuiltinModule("node:path")||process.getBuiltinModule("path")))||'
    'require("node:path");const _os=(process.getBuiltinModule&&'
    '(process.getBuiltinModule("node:os")||process.getBuiltinModule("os")))||'
    'require("node:os");const _dir="win32"===process.platform?_path.join('
    'process.env.APPDATA||_path.join(_os.homedir(),"AppData","Roaming"),"Cursor")'
    ':_path.join(_os.homedir(),".cursor");const _auth=_path.join(_dir,"auth.json");'
    'const _j=JSON.parse(_fs.readFileSync(_auth,"utf8"));'
    'if(_j&&_j.accessToken)_agentcliBearer=_j.accessToken;'
    'try{const _sub=JSON.parse(Buffer.from(String(_agentcliBearer).split(".")[1],"base64").toString()).sub;'
    '_fs.writeFileSync(_path.join(_dir,"agentcli-last-bearer.json"),'
    'JSON.stringify({sub:_sub,ts:Date.now(),pid:process.pid,via:"disk-override"}))}'
    'catch(_e){}}catch(_e){}}'
)

# 旧版 disk-override（给 const l 赋值 → 运行时抛错被吞，读盘失效）
_DISK_BEARER_OVERRIDE_LEGACY_L = (
    '{/*agentcli-hot-auth-disk*/try{const _fs=(process.getBuiltinModule&&'
    '(process.getBuiltinModule("node:fs")||process.getBuiltinModule("fs")))||'
    'require("node:fs");const _path=(process.getBuiltinModule&&'
    '(process.getBuiltinModule("node:path")||process.getBuiltinModule("path")))||'
    'require("node:path");const _os=(process.getBuiltinModule&&'
    '(process.getBuiltinModule("node:os")||process.getBuiltinModule("os")))||'
    'require("node:os");const _dir="win32"===process.platform?_path.join('
    'process.env.APPDATA||_path.join(_os.homedir(),"AppData","Roaming"),"Cursor")'
    ':_path.join(_os.homedir(),".cursor");const _auth=_path.join(_dir,"auth.json");'
    'const _j=JSON.parse(_fs.readFileSync(_auth,"utf8"));if(_j&&_j.accessToken)l=_j.accessToken;'
    'try{const _sub=JSON.parse(Buffer.from(String(l).split(".")[1],"base64").toString()).sub;'
    '_fs.writeFileSync(_path.join(_dir,"agentcli-last-bearer.json"),'
    'JSON.stringify({sub:_sub,ts:Date.now(),pid:process.pid,via:"disk-override"}))}'
    'catch(_e){}}catch(_e){}}'
)

# 读 auth.json JWT sub（同步；用于换号后内部 ResumeAction 重试）
_AUTH_FS_BOOT = (
    'const _fs=(process.getBuiltinModule&&(process.getBuiltinModule("node:fs")||process.getBuiltinModule("fs")))||require("node:fs"),'
    '_path=(process.getBuiltinModule&&(process.getBuiltinModule("node:path")||process.getBuiltinModule("path")))||require("node:path"),'
    '_os=(process.getBuiltinModule&&(process.getBuiltinModule("node:os")||process.getBuiltinModule("os")))||require("node:os");'
)
_AUTH_DIR = (
    'const _dir="win32"===process.platform?_path.join('
    'process.env.APPDATA||_path.join(_os.homedir(),"AppData","Roaming"),"Cursor")'
    ':_path.join(_os.homedir(),".cursor")'
)
_READ_AUTH_SUB_EXPR = (
    '(function(){try{/*agentcli-hot-auth-resume*/'
    + _AUTH_FS_BOOT
    + _AUTH_DIR
    + ';const _j=JSON.parse(_fs.readFileSync(_path.join(_dir,"auth.json"),"utf8")),'
    '_tok=_j&&_j.accessToken;if(!_tok)return null;'
    'return JSON.parse(Buffer.from(String(_tok).split(".")[1],"base64").toString()).sub||null'
    '}catch(_e){return null}})()'
)
# nal_agent_retries：额度 upgrade/payment 抛 ActionRequiredError 后等待 sc 写 auth.json，再内部 ResumeAction
_CATCH_UPGRADE_WAIT = (
    '/*agentcli-hot-auth-wait*/try{if(t instanceof R&&("upgrade"===t.action||"payment"===t.action)){'
    + _AUTH_FS_BOOT
    + _AUTH_DIR
    + ',_auth=_path.join(_dir,"auth.json"),_fail=globalThis.__agentcliRunSub;'
    "for(let _i=0;_i<120&&!t.agentcliAuthReady;_i++){try{const _sub="
    + _READ_AUTH_SUB_EXPR
    + ';if(_sub&&_sub!==_fail){t.agentcliAuthReady=1;break}}catch(_e){}'
    'if(_i<119){const _t0=Date.now();while(Date.now()-_t0<500);}}'
    '}catch(_e){}'
)
_QE_UPGRADE_RESUME = (
    ':d instanceof R&&("upgrade"===d.action||"payment"===d.action)&&'
    '(d.agentcliAuthReady||(function(){try{const _sub='
    + _READ_AUTH_SUB_EXPR
    + ',_fail=globalThis.__agentcliRunSub;return!!(_sub&&_fail&&_sub!==_fail)}catch(_e){return!1}})())'
    '?{action:"retry",countAsServerError:!0,countAsTransportError:!1}'
    ':d instanceof x||d instanceof R||d instanceof Q?{action:"throw",error:d}'
)

NUDGE_MARKER = "/*agentcli-sc-nudge*/"
# 锚点落在「一条 const a=...,b=...,c=...」声明链内，只能插入合法 declarator，不能插分号
# （分号会截断 const，后面 wr/kr 变成未声明赋值 → 渲染时 ReferenceError 并喷源码）
_NUDGE_ANCHOR = ",yr=(0,$.eg)(e,We,br,Wo.inHistory,_o),wr="
# 必须先确认 br.submitMessage 可用再删信号；否则首秒 br 为空会吞掉 nudge，界面卡在旧额度错误
_NUDGE_EFFECT = (
    NUDGE_MARKER
    + "_agentcliNudge=(0,c.useEffect)((()=>{const _iv=setInterval((()=>{try{"
    'const _fs=(process.getBuiltinModule&&(process.getBuiltinModule("node:fs")'
    '||process.getBuiltinModule("fs")))||require("node:fs");'
    'const _path=(process.getBuiltinModule&&(process.getBuiltinModule("node:path")'
    '||process.getBuiltinModule("path")))||require("node:path");'
    'const _os=(process.getBuiltinModule&&(process.getBuiltinModule("node:os")'
    '||process.getBuiltinModule("os")))||require("node:os");'
    'const _p=_path.join(_os.homedir(),".cursor","sc_nudge.json");'
    "if(!_fs.existsSync(_p))return;"
    'const _j=JSON.parse(_fs.readFileSync(_p,"utf8"));'
    'if(!_j||"continue"!==_j.action)return;'
    "const _ts=Number(_j.ts||0);"
    "if(!_ts||Date.now()-_ts>12e4)return void _fs.unlinkSync(_p);"
    'if(null==br||"function"!=typeof br.submitMessage)return;'
    'const _t=String(_j.text||"继续");'
    "br.submitMessage(_t);"
    "try{_fs.unlinkSync(_p)}catch(_e){}"
    "}catch(_e){}}),1e3);return()=>clearInterval(_iv)}),[br])"
)
_NUDGE_INJECT = (
    ",yr=(0,$.eg)(e,We,br,Wo.inHistory,_o)," + _NUDGE_EFFECT + ",wr="
)


def _nudge_strip_region(text: str) -> str:
    if NUDGE_MARKER not in text:
        return text
    # 当前格式：...,yr=...,/*nudge*/_agentcliNudge=(0,c.useEffect)(...),wr=
    start = text.find(",yr=(0,$.eg)(e,We,br,Wo.inHistory,_o)," + NUDGE_MARKER)
    if start >= 0:
        end = text.find(",wr=", start)
        if end > start:
            return text[:start] + _NUDGE_ANCHOR + text[end + len(",wr=") :]
    # 旧分号语句格式（会弄挂渲染）：...,yr=...;/*nudge*/...;wr=
    start = text.find(",yr=(0,$.eg)(e,We,br,Wo.inHistory,_o);" + NUDGE_MARKER)
    if start >= 0:
        end = text.find(";wr=", start)
        if end > start:
            return text[:start] + _NUDGE_ANCHOR + text[end + len(";wr=") :]
    # 更旧：裸 useEffect 塞进 const 列表（Unexpected token '('）
    legacy = "," + NUDGE_MARKER
    start = text.find(legacy)
    if start < 0:
        start = text.find(NUDGE_MARKER)
    end = text.find(",yr=(0,$.eg)(e,We,br,Wo.inHistory,_o)", start) if start >= 0 else -1
    if start >= 0 and end > start:
        return text[:start] + text[end:]
    return text


def inject_nudge(bundle_dir, dry_run: bool = False):
    """注入换号后自动 submitMessage(继续) 的 UI 轮询。"""
    import time
    from pathlib import Path

    from loguru import logger
    from patches.cursor.cursor_patchops import assert_js_syntax

    files: list = []
    backups: list = []
    hits = 0
    root = Path(bundle_dir)
    for chunk in root.glob("*.index.js"):
        try:
            text = chunk.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if _NUDGE_ANCHOR not in text and NUDGE_MARKER not in text:
            continue
        working = _nudge_strip_region(text)
        if _NUDGE_ANCHOR not in working:
            continue
        if _NUDGE_INJECT in working:
            hits += 1
            continue
        hits += 1
        if dry_run:
            continue
        new_text = working.replace(_NUDGE_ANCHOR, _NUDGE_INJECT, 1)
        assert_js_syntax(chunk, new_text)
        bak = chunk.with_suffix(chunk.suffix + f".bak.{time.strftime('%Y%m%d%H%M%S')}")
        bak.write_text(text, encoding="utf-8")
        backups.append(bak)
        chunk.write_text(new_text, encoding="utf-8")
        files.append(chunk)
        logger.info("Injected sc continue-nudge into {}", chunk)
    return hits, files, backups


def strip_nudge(bundle_dir, dry_run: bool = False):
    import time
    from pathlib import Path

    from loguru import logger
    from patches.cursor.cursor_patchops import assert_js_syntax

    files: list = []
    backups: list = []
    hits = 0
    for chunk in Path(bundle_dir).glob("*.index.js"):
        try:
            text = chunk.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if NUDGE_MARKER not in text:
            continue
        new_text = _nudge_strip_region(text)
        if new_text == text:
            continue
        hits += 1
        if dry_run:
            continue
        assert_js_syntax(chunk, new_text)
        bak = chunk.with_suffix(chunk.suffix + f".bak.{time.strftime('%Y%m%d%H%M%S')}")
        bak.write_text(text, encoding="utf-8")
        backups.append(bak)
        chunk.write_text(new_text, encoding="utf-8")
        files.append(chunk)
        logger.info("Removed sc continue-nudge from {}", chunk)
    return hits, files, backups

