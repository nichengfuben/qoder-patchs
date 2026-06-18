# Documentation Index / 文档索引

Welcome to the qoder-patchs documentation. This index provides an overview of all available documentation.
欢迎阅读 qoder-patchs 文档. 本索引提供所有可用文档的概览.

---

## Documentation Structure / 文档结构

### Core / 核心

| Document | Description | 说明 |
|----------|-------------|------|
| [Architecture](core/ARCHITECTURE.md) | System architecture, component diagram, data flow, configuration system, extension points | 系统架构, 组件图, 数据流, 配置系统, 扩展点 |

### Patches / 补丁

| Document | Description | 说明 |
|----------|-------------|------|
| [Patch Development Guide](patches/guide.md) | Step-by-step guide to creating new patches, PatchBase interface reference, testing, examples | 创建新补丁的分步指南, PatchBase 接口参考, 测试, 示例 |

### CLI / 命令行界面

| Document | Description | 说明 |
|----------|-------------|------|
| [Theme Customization](cli/theme.md) | Blue palette explanation, color modification guide, charmap usage, banner customization | 蓝色调色板说明, 颜色修改指南, charmap 用法, 横幅定制 |

---

## Quick Reference / 快速参考

### Source Code Layout / 源码布局

```
src/qoder_patchs/
 +-- core/               Core infrastructure (config, engine, registry, patch_base)
 +-- cli/                CLI interface (app, menu, ui, theme, charmap)
 +-- patches/            Patch implementations
 +-- utils/              Utilities (backup, paths, platform, logging)
```

### Key Entry Points / 关键入口

| Entry Point | Module | Description |
|-------------|--------|-------------|
| `python main.py` | `main.py` | Interactive mode / 交互模式 |
| `qoder-patchs` | `cli.app:typer_app` | Installed CLI command |
| `qp` | `cli.app:typer_app` | Shorthand CLI command |
| `python -m qoder_patchs` | `__main__.py` | Module execution |

### Configuration Priority / 配置优先级

1. `--config` CLI argument / `--config` CLI 参数
2. `QODER_PATCHS_CONFIG` environment variable / `QODER_PATCHS_CONFIG` 环境变量
3. Project root `config.toml` / 项目根 `config.toml`
4. User config directory (platformdirs) / 用户配置目录
5. Built-in defaults / 内置默认值

---

## External Resources / 外部资源

- **Repository**: https://github.com/nichengfuben/qoder-patchs
- **PyPI**: (pending publication)
- **License**: MIT
