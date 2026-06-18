```
 ██████╗  ██████╗ ██████╗ ███████╗██████╗
██╔═══██╗██╔══██╗██╔══██╗██╔════╝██╔══██╗
██║   ██║██║  ██║██████╔╝█████╗  ██████╔╝
██║▄▄ ██║██║  ██║██╔══██╗██╔══╝  ██╔══██╗
╚██████╔╝██████╔╝██║  ██║███████╗██║  ██║
 ╚══▀▀═╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝
```

# Qoder Patch Manager (qoder-patchs)

**Qoder CLI Patch Management Tool -- Interactive Blue CLI, Extensible Patch System**
**Qoder CLI 补丁管理工具 -- 交互式蓝色 CLI, 可扩展补丁系统**

---

## Problem / 问题背景

Qoder CLI displays a "Windows 10 detected" warning on startup when running on Windows 10 systems. The original fix was a Bash script (`patch-win10-warning.sh`) that depended on `grep -P` (PCRE), `perl`, and MSYS path utilities -- fragile dependencies that break across environments.

Qoder CLI 在 Windows 10 系统上启动时会显示 "Windows 10 detected" 警告. 最初的修复方案是一个 Bash 脚本 (`patch-win10-warning.sh`), 依赖 `grep -P` (PCRE), `perl` 和 MSYS 路径工具 -- 这些脆弱的依赖在不同环境中容易出错.

**qoder-patchs** rewrites the solution as a portable Python CLI with zero external system dependencies, an interactive blue-themed interface, and an extensible patch framework that makes adding new patches trivial.

**qoder-patchs** 将解决方案重写为可移植的 Python CLI, 零外部系统依赖, 配备交互式蓝色主题界面, 以及可扩展的补丁框架, 使添加新补丁变得非常简单.

---

## Features / 功能特性

| Feature | Description | 说明 |
|---------|-------------|------|
| Interactive CLI | Typer + Rich + Questionary with arrow-key navigation | 交互式菜单, 方向键导航 |
| Blue Theme | Professional blue palette with gradient ASCII banner | 专业蓝色调色板 + 渐变 ASCII 横幅 |
| Extensible Patches | Auto-discovery via `pkgutil` + `entry_points` | 通过 `pkgutil` + `entry_points` 自动发现 |
| Portable Config | Project-root `config.toml` with 5-level priority | 项目根 `config.toml`, 5 级优先级查找 |
| Backup & Rollback | Timestamped backups with automatic retention | 带时间戳的备份, 自动清理保留策略 |
| Dry-Run Mode | Preview changes without modifying files | 预览模式, 不修改文件 |
| JSON Output | `--json` flag for scripting/CI integration | `--json` 标志供脚本/CI 集成 |
| Win10 Patch | Suppress Windows 10 warning (ported from Bash) | 抑制 Win10 警告 (从 Bash 移植) |
| 127 Tests | Comprehensive test suite with pytest | 全面的 pytest 测试套件 |

---

## Quick Start / 快速开始

### Installation / 安装

```bash
# Clone the repository / 克隆仓库
git clone https://github.com/nichengfuben/qoder-patchs.git
cd qoder-patchs

# Install in development mode (includes dev dependencies) / 以开发模式安装 (包含开发依赖)
pip install -e ".[dev]"

# Run the interactive CLI / 运行交互式 CLI
python main.py
```

### Alternative entry points / 其他入口

```bash
# After pip install, two CLI commands are available:
# pip 安装后, 有两个 CLI 命令可用:
qoder-patchs          # full name / 完整名
qp                    # shorthand / 简写

# Or run as a Python module / 或作为 Python 模块运行:
python -m qoder_patchs
```

---

## Usage / 使用方法

### Interactive Mode (default) / 交互模式 (默认)

```bash
python main.py
```

Launches the interactive menu with an ASCII art banner:
启动交互式菜单, 显示 ASCII 艺术横幅:

```
  QODER

  Qoder Patch Manager v2.0.0
  ─────────────────────────────────────────────────────

  Please select an operation: (arrow keys, Enter to confirm)
  > Apply patches        (应用补丁)
    View patch status    (查看补丁状态)
    Rollback patches     (回滚补丁)
    Edit configuration   (修改配置)
    About                (关于)
    Exit                 (退出)
```

### CLI Commands / 命令行

```bash
# Apply a specific patch / 应用指定补丁
python main.py apply win10-warning

# Apply all patches / 应用所有补丁
python main.py apply --all

# Preview mode (no file changes) / 预览模式 (不修改文件)
python main.py apply --all --dry-run

# Force re-apply already-applied patches / 强制重新应用已应用的补丁
python main.py apply --all --force

# View patch status / 查看补丁状态
python main.py status

# View patch status as JSON / 以 JSON 格式查看补丁状态
python main.py status --json

# Rollback a patch / 回滚补丁
python main.py rollback win10-warning

# Show current configuration / 显示当前配置
python main.py config show

# Modify a configuration value / 修改配置项
python main.py config set patch.backup_count 5

# Show about information / 显示关于信息
python main.py about
```

### Global Options / 全局选项

```bash
# Verbose output (DEBUG level) / 详细输出 (DEBUG 级别)
python main.py --verbose status

# Use a custom config file / 使用自定义配置文件
python main.py --config /path/to/config.toml status
```

---

## Configuration / 配置

Configuration uses TOML format with 5-level priority lookup:
配置使用 TOML 格式, 5 级优先级查找:

1. `--config` CLI argument / `--config` CLI 参数
2. `QODER_PATCHS_CONFIG` environment variable / `QODER_PATCHS_CONFIG` 环境变量
3. Project root `config.toml` / 项目根 `config.toml`
4. User config directory (platformdirs) / 用户配置目录 (platformdirs)
5. Built-in defaults / 内置默认值

### Example `config.toml`

```toml
[patch]
auto_backup = true        # Backup before patching / 补丁前备份
backup_count = 3          # Backups to retain (1-10) / 保留备份数 (1-10)
dry_run_default = false   # Preview mode by default / 默认预览模式
force_reapply = false     # Re-apply already-applied patches / 重新应用已应用补丁

[ui]
theme = "blue"            # Theme name / 主题名
show_banner = true        # Show ASCII banner on startup / 启动时显示 ASCII 横幅
verbose = false           # Verbose output / 详细输出
use_color = true          # Colored output / 彩色输出

[paths]
# bundle_dir = "C:/..."  # Manual bundle path (auto-detect if omitted) / 手动设置 bundle 路径
backup_dir = ".backup"    # Backup directory / 备份目录
# log_file = "logs/qoder-patchs.log"  # Log file path / 日志文件路径

[persistence]
scheduled_task = true     # Windows auto-start task / Windows 开机自启任务
npm_hooks = true          # npm post-install hooks / npm 安装后钩子
on_update_repatch = true  # Auto re-patch after CLI update / CLI 更新后自动重新补丁
```

A commented template is provided at `config.template.toml`.
带注释的模板文件位于 `config.template.toml`.

---

## Patch Development / 补丁开发

Creating a new patch is straightforward. See [docs-src/patches/guide.md](docs-src/patches/guide.md) for the full guide.

创建新补丁非常简单. 完整指南请参阅 [docs-src/patches/guide.md](docs-src/patches/guide.md).

### Quick Example / 快速示例

```python
# src/qoder_patchs/patches/my_patch.py
from pathlib import Path
from qoder_patchs.core import PatchBase, PatchMetadata, PatchResult, PatchStatus

class MyPatch(PatchBase):
    @property
    def metadata(self) -> PatchMetadata:
        return PatchMetadata(
            name="my-patch",
            display_name="My Custom Patch",
            description="Does something useful",
            version="1.0.0",
            author="your-name",
            target_files=("target.js",),
            tags=("custom",),
        )

    def check(self, bundle_dir: Path) -> PatchStatus:
        # Inspect files to determine if patch is applied
        ...

    def apply(self, bundle_dir: Path, dry_run: bool = False) -> PatchResult:
        # Apply the patch
        ...

    def rollback(self, bundle_dir: Path, backup_path=None) -> PatchResult:
        # Restore from backup
        ...
```

Register via entry point in `pyproject.toml`:
通过 `pyproject.toml` 的 entry point 注册:

```toml
[project.entry-points."qoder_patchs.patches"]
my-patch = "qoder_patchs.patches.my_patch:MyPatch"
```

---

## Architecture / 架构

See [docs-src/core/ARCHITECTURE.md](docs-src/core/ARCHITECTURE.md) for the full architecture document.
完整架构文档请参阅 [docs-src/core/ARCHITECTURE.md](docs-src/core/ARCHITECTURE.md).

```
src/qoder_patchs/
 +-- core/               # Core infrastructure / 核心基础设施
 |   +-- patch_base.py   #   PatchBase ABC + metadata / 补丁抽象基类
 |   +-- registry.py     #   Auto-discovery registry / 自动发现注册表
 |   +-- engine.py       #   Patch execution engine / 补丁执行引擎
 |   +-- config.py       #   TOML configuration / TOML 配置管理
 +-- cli/                # CLI interface / CLI 界面
 |   +-- app.py          #   Typer commands / Typer 命令定义
 |   +-- menu.py         #   Questionary menus / Questionary 菜单
 |   +-- ui.py           #   BlueCLI output / BlueCLI 输出封装
 |   +-- theme.py        #   Blue theme + palette / 蓝色主题 + 调色板
 |   +-- charmap.py      #   ASCII art rendering / ASCII 艺术渲染
 +-- patches/            # Patch implementations / 补丁实现
 |   +-- win10_warning.py  # Win10 warning suppression / Win10 警告抑制
 |   +-- _templates.py     # Development templates / 开发模板
 +-- utils/              # Utilities / 工具函数
     +-- backup.py       #   Backup manager / 备份管理器
     +-- paths.py        #   Path resolution / 路径解析
     +-- platform.py     #   Platform helpers / 平台辅助
     +-- logging.py      #   Loguru setup / Loguru 配置
```

---

## Requirements / 环境要求

- **Python**: 3.11+ (3.12, 3.13, 3.14 supported / 支持)
- **OS**: Windows 10/11 (primary), Linux, macOS
- **Runtime**: `npm` and `node` (for locating Qoder CLI bundle / 用于定位 Qoder CLI bundle)

### Python Dependencies / Python 依赖

| Package | Version | Purpose | 用途 |
|---------|---------|---------|------|
| typer | >=0.12.0 | CLI framework | CLI 框架 |
| rich | >=13.0.0 | Terminal formatting | 终端格式化 |
| questionary | >=2.0.0 | Interactive prompts | 交互式提示 |
| platformdirs | >=4.0.0 | Platform directories | 平台目录 |
| pydantic | >=2.0.0 | Config validation | 配置验证 |
| tomli-w | >=1.0.0 | TOML serialization | TOML 序列化 |
| loguru | >=0.7.0 | Logging | 日志 |

---

## Testing / 测试

```bash
# Run all tests / 运行所有测试
pytest

# With coverage / 带覆盖率
pytest --cov=qoder_patchs

# Verbose output / 详细输出
pytest -v
```

---

## Documentation / 文档

- [Documentation Index / 文档索引](docs-src/INDEX.md)
- [Architecture / 架构](docs-src/core/ARCHITECTURE.md)
- [Patch Development Guide / 补丁开发指南](docs-src/patches/guide.md)
- [Theme Customization / 主题定制](docs-src/cli/theme.md)

---

## License / 许可证

MIT License -- Copyright (c) 2025 nichengfuben

See [LICENSE](LICENSE) for details.
详情请参阅 [LICENSE](LICENSE).
