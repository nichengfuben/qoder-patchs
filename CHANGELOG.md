# Changelog

本文件记录 AgentCLI Patchs 的发布变更。产品说明见 [README.md](README.md)。

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
- 原 Qoder `win10-warning` 补丁保留

## 2.0.0

- Qoder Patch Manager：Win10 警告抑制、交互 CLI、可扩展补丁框架
