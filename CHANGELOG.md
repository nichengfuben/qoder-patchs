# Changelog

本文件记录 AgentCLI Patchs 的发布变更。产品说明见 [README.md](README.md)。

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
