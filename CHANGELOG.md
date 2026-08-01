# Changelog

本文件记录 Patcher（原 AgentCLI Patchs）的发布变更。产品说明见 [README.md](README.md)。

## 2.5.3

- **CLI UI 下沉 echotools**：移除 `questionary` 与本地 `charmap.py`；交互菜单、ASCII 横幅、主题与配置编辑改由 `echotools[console]` 驱动
- **新增** `cli/echotools_bridge.py`：同步 select/confirm、Patcher 渐变主题、配置 flatten/coerce 工具
- **statusLine**：ANSI 宽度/截断改用 `echotools.TextUtils`

## 2.5.2

- **换号自动继续**：换号成功后写入 `~/.cursor/sc_nudge.json`，Agent UI 轮询并 `submitMessage("继续")`，无需手动再说一遍
- **hot-auth disk-override**：外层 `const l` 不再直接赋值（此前赋值被吞导致读盘失效），改为 `var _agentcliBearer`
- **阈值**：默认 `usage_threshold` 95% → 90%

## 2.5.1

- **CLI**：应用/状态/回滞按补丁解析目标目录；`cursor-agent` 不再依赖 Qoder `bundle`（Linux 无 Qoder 时可直接打 Agent 补丁）
- **CI**：`tree-sitter-language-pack` 仅在 Python ≥3.10 安装（该包不支持 3.8/3.9），修复 3.8 矩阵失败
- **状态**：`interval`/`footer` UI 片段在当前 Agent 版本不存在时视为不适用，不再误报「部分应用」
- **statusLine**：窄 `render_width` 时优先缩短进度条并保留 `HH:MM:SS`，避免时间被裁成 `…`

## 2.5.0

- **跨平台**：`cursor-agent` 补丁支持 Windows / Linux / macOS
  - 安装根：Win=`%LOCALAPPDATA%\cursor-agent`；Unix=`~/.local/share/cursor-agent`
  - Unix：安装 `sc` / `sc-statusline` / `sc-autoboot.sh`；将 `versions/<ver>/cursor-agent` 包装为 shell（真实二进制 → `cursor-agent.bin`）
  - `/sc` spawn 与 statusLine 命令按平台选择可执行文件
  - `sc auto` 后台：Unix 使用 `start_new_session`
- **auth 对齐**：Linux/macOS 的 `auth.json` 与 JS hot-auth 一致，固定为 `~/.cursor`（不再用 XDG `~/.config/cursor`）
- **Python**：`requires-python >=3.8`；`<3.11` 使用 `tomli`；CI 矩阵 3.8–3.14
- 启动器写入统一无 BOM；Unix shell 仅 LF，Windows `.cmd` 用 CRLF

## 2.4.6

- **statusLine**：`sc-statusline.cmd` / `sc.ps1` 改为无 BOM 写入；UTF-8 BOM 会破坏 `@echo off`，导致 Agent 底栏刷出整段 cmd 回显并冻住时钟/进度条
- `sc_status.json` / `sc_instances.json` 读取改用 `utf-8-sig`，兼容被误写入 BOM 的状态文件

## 2.4.5

- **交互菜单**：应用/回滞补丁改用方向键+Enter 单选（含「全部」），避免 checkbox 未按空格勾选导致“选中不生效”
- 交互应用时默认强制重打已 APPLIED 的补丁

## 2.4.4

- **SC 配置目录**：`config.json` / `sc_status.json` / `sc_auto.*` 迁至 `~/.cursor`（与 `cli-config`、`sc_instances` 同目录）；`auth.json` 仍在平台 auth 目录（Windows：`%APPDATA%\Cursor`）
- 启动时若新路径缺失且旧 auth 目录仍有 SC 文件，自动复制（不删源）

## 2.4.3

- achecker：`encoding` 迁入 `sc.core`；`format_status_lines` 迁入 `statusline_fast`，压缩 `status_store` 行数并满足 `src/sc` 子项上限

## 2.4.2

- **statusLine**：恢复 `sc.statusline_fast` 兼容入口（2.4.0 误删后旧 `sc-statusline.cmd` 会刷新失败导致底栏冻在最后一帧）
- statusLine 读 stdin 加短超时，避免管道未关闭时挂死
- launcher 模板改回 `-m sc.statusline_fast`

## 2.4.1

- **cursor-agent 测试**：以未打补丁的 `2026.07.23-e383d2b` 源码 gzip fixture 验证 hot-auth / statusline / footer / slash / ps1
- 修复 `cursor_patchops` 误留 `self` 导致 UI chunk 补丁无法调用
- CI：去除若干源文件 UTF-8 BOM；展平 menu / status badge 嵌套以通过 Linux achecker
- Release 工作流：tag 已存在时改为上传构建产物

## 2.4.0

- 项目更名为 **Patcher**（包名 `patcher`，仓库 `nichengfuben/Patcher`）
- CLI 入口 `patcher`；保留 `agentcli-patchs` / `acp` / `qp` 兼容
- 环境变量优先 `PATCHER_*`，兼容 `AGENTCLI_PATCHS_*`
- `src/sc` 拆为 `core/` + `run/`；`cursor-agent` 补丁拆模块以通过 achecker
- 新增 GitHub Actions CI（pytest）与 tag Release 工作流

## 2.3.5

- **hot-auth 无缓存**：file ``getAccessToken`` / refresh / apiKey / getAll 只 ``readAuthData``，不再写 ``cached*``
- keychain / memory getter 一律空；memory ``getAllCredentials`` 不再回落进程内 token
- 凭证路径仅 ``auth.json``；与账号类型无关

## 2.3.4

- 补丁重命名：`win10-warning` → **`remove-qoder-warning`**（`RemoveQoderWarningPatch`）
- Star Cursor：`base_url` / `api_keys` **仅读** `%APPDATA%\Cursor\config.json`；移除代码内服务地址与本机路径硬编码
- 可选播种：环境变量 `AGENTCLI_SC_CONFIG_SRC`；statusline/sc 启动器用 apply 时的项目 `src` 路径，不再写死盘符
- hot-auth：升级 disk Bearer 为 `getBuiltinModule`；补齐 `credentialManager` Bearer 三处强制读盘

## 2.3.2

- GitHub 仓库更名为 **AgentCLI-Patchs**
- 新增 `sc doctor`：检查 hot-auth/disk Bearer 标记、`auth.sub` 与 `agentcli-last-bearer.json` 对照

## 2.3.1

- **hot-auth disk Bearer**：agent 主链路另有内联 `ephemeralToken:R`；每次设 `Authorization` 前 `readFileSync(auth.json)` 强制覆盖，并写 `agentcli-last-bearer.json` 对照 `sub`

## 2.3.0

- **hot-auth v2**：掐断 `auth-refresh` ephemeral / apiKeyOverride；Zn 不再回落内存 token；memory store getter 兜底为空；keychain `getAllCredentials` 去短路
- 禁用 `cursor-agent.ps1` 的 `NODE_COMPILE_CACHE`，apply 时清理 `%LOCALAPPDATA%\cursor-compile-cache`
- 补丁自测：原串 → `apply_hot_auth_replacements` 断言；`index.js` 写入前 `node --check`
- `sc status` 输出当前 `auth.json` JWT `sub`，便于对照换号是否生效

## 2.2.1

- 多 AgentCLI 实例：`~/.cursor/sc_instances.json`（uuidv7 + 心跳）；>10s 未心跳自动下线
- 仅最早上线且在线的实例作为 leader 跑 `auto` 换号/用量；其余监听保活；leader 同步写回用量
- 修复多 `sc auto` 并发换号异常；`PULL`/`SWITCH` 不再并排展示旧账号 100% 条
- `auth.json` 原子重写 + utime，配合热读补丁换号立即生效

## 2.2.0

- 删除全部 Agent `/sc` slash；进入 `ag` 时由 `cursor-agent.cmd` 自动后台 `sc auto`
- apply 时从 `Common/config.json`（client.py）复制到 `%APPDATA%\Cursor\config.json`

## 2.1.5

- 移除冗余 `sc usage`（用量由 `/sc status`、statusLine、`auto` 覆盖）

## 2.1.4

- 全方位 UTF-8：`sc` 启动强制 UTF-8 stdio；`sc.cmd`/`sc.ps1`/`sc-statusline` 设 `PYTHONUTF8`+`chcp 65001`；`/sc` spawn 注入同环境，修复 Agent 内中文乱码

## 2.1.3

- statusLine 改为一行紧凑格式（对齐 client.py）：突出 `↻` 刷新额度与 `SWITCH`/`PULL` 换号
- `parse_usage` 对齐 client：（auto+api）/2、OK/NEAR_LIMIT/LIMIT/UNLIMITED

## 2.1.2

- `sc`：写入 `sc_status.json` 实时状态；新增 `sc statusline` 供 Agent CLI statusLine
- apply 安装 `sc-statusline.cmd` 并合并 `~/.cursor/cli-config.json` 的 `statusLine`（完整账号/用量/auto 动作）

## 2.1.1

- `cursor-agent`：向 Agent slash 面板注入 builtin `/sc`（修复仅装 `sc.cmd` 时交互框 `/sc` 落到技能列表的问题）
- `sc.ps1`：安装时写入仓库 `src` 的绝对 `PYTHONPATH`

## 2.1.0 — 2026-07-31

### Changed
- 仓库/包更名为 **AgentCLI-Patchs** / `agentcli-patchs`
- 源码改为 `src/{cli,core,patches,sc,utils}` 扁平包布局，导入改为顶层包名
- README 与 CHANGELOG 分离

### Added
- 补丁 `cursor-agent`：AuthStorage 去缓存热读 `auth.json`；安装 `sc.cmd`/`sc.ps1`
- 便携 `/sc`（`sc` CLI）：`pull` / `usage` / `token` / `status` / `addkey` / `auto`
- `config.json` 与 cursor-agent `auth.json` 同级（`%APPDATA%\Cursor\`）

### Notes
- 原 Qoder `remove-qoder-warning` 补丁保留

## 2.0.0

- Qoder Patch Manager：Win10 警告抑制、交互 CLI、可扩展补丁框架
