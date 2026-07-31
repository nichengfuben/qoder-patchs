# Changelog

本文件记录 AgentCLI Patchs 的发布变更。产品说明见 [README.md](README.md)。

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
