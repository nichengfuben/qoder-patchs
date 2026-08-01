from __future__ import annotations

"""UI chunk patch patterns (statusline/footer/slash)."""

STATUS_INTERVAL_MARKER = "/*agentcli-status-interval*/"
FOOTER_KEEP_MARKER = "/*agentcli-footer-keep*/"
SLASH_MARKER = "/*agentcli-sc-slash*/"

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

NUDGE_MARKER = "/*agentcli-sc-nudge*/"
# 紧挨 slash UI 的 submitMessage 之后：轮询 ~/.cursor/sc_nudge.json 自动提交「继续」
_NUDGE_ANCHOR = ",yr=(0,$.eg)(e,We,br,Wo.inHistory,_o)"
_NUDGE_INJECT = (
    ","
    + NUDGE_MARKER
    + "(0,c.useEffect)((()=>{const _iv=setInterval((()=>{try{"
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
    "_fs.unlinkSync(_p);"
    'const _t=String(_j.text||"继续");'
    "null==br||null==br.submitMessage||br.submitMessage(_t)"
    "}catch(_e){}}),1e3);return()=>clearInterval(_iv)}),[br])"
    + _NUDGE_ANCHOR
)
