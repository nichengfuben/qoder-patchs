# Documentation Index

AgentCLI Patchs 文档索引。产品用法见仓库根 [README.md](../README.md)，版本变更见 [CHANGELOG.md](../CHANGELOG.md)。

## Core

| Document | Description |
|----------|-------------|
| [Architecture](core/ARCHITECTURE.md) | 架构、配置优先级、扩展点 |

## Patches

| Document | Description |
|----------|-------------|
| [Patch Development Guide](patches/guide.md) | 编写新补丁（`src/patches/`） |

## CLI

| Document | Description |
|----------|-------------|
| [Theme](cli/theme.md) | 蓝色主题与 charmap |

## 源码布局

```
src/
  cli/       # Typer / 交互菜单
  core/      # engine / registry / PatchBase
  patches/   # remove-qoder-warning, cursor-agent
  sc/        # /sc 便携换号
  utils/     # paths / backup / platform
```

## 入口

| Entry | Module |
|-------|--------|
| `python main.py` | `cli.app:typer_app` |
| `agentcli-patchs` / `acp` / `qp` | 同上 |
| `sc` / `/sc` | `sc.cli:main` |
| `python -m cli` | `cli` |
| `python -m sc` | `sc` |
