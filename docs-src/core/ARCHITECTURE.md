# Architecture / 架构

This document describes the system architecture of qoder-patchs, including component relationships, data flow, configuration system, and extension points.
本文档描述 qoder-patchs 的系统架构, 包括组件关系, 数据流, 配置系统和扩展点.

---

## Component Diagram / 组件图

```
+-----------------------------------------------------------------------+
|                          User / 用户                                   |
+-----------------------------------------------------------------------+
        |                                          |
        v                                          v
+------------------+                    +--------------------+
| Interactive Mode |                    | CLI Commands       |
| (menu.py)        |                    | (app.py)           |
|                  |                    |                    |
| - main_menu()    |                    | - apply            |
| - patch_select() |                    | - status           |
| - confirm()      |                    | - rollback         |
| - config_menu()  |                    | - config show/set  |
+--------+---------+                    | - about            |
         |                              +---------+----------+
         |                                         |
         +------------------+----------------------+
                            |
                            v
                  +-------------------+
                  | BlueCLI (ui.py)   |
                  |                   |
                  | - banner()        |
                  | - success/error() |
                  | - status_table()  |
                  | - table()         |
                  +---------+---------+
                            |
                            v
                  +-------------------+
                  | PatchEngine       |
                  | (engine.py)       |
                  |                   |
                  | - apply()         |
                  | - apply_all()     |
                  | - rollback()      |
                  | - status()        |
                  | - status_all()    |
                  +----+---------+----+
                       |         |
              +--------+         +--------+
              v                           v
+------------------------+    +------------------------+
| PatchRegistry          |    | BackupManager          |
| (registry.py)          |    | (backup.py)            |
|                        |    |                        |
| - register()           |    | - create_backup()      |
| - get() / get_all()    |    | - cleanup_old()        |
| - discover_builtin()   |    | - restore_from()       |
| - discover_entry_pts() |    | - list_backups()       |
+-----------+------------+    +------------------------+
            |
            v
+------------------------+
| PatchBase (ABC)        |
| (patch_base.py)        |
|                        |
| - metadata (property)  |
| - check()              |
| - apply()              |
| - rollback()           |
| - validate()           |
| - info()               |
+-----------+------------+
            |
            v (concrete implementations / 具体实现)
+------------------------+
| Win10WarningPatch       |
| (win10_warning.py)      |
|                         |
| target_files:           |
| - qodercli.js           |
| - qoder-worker-runtime  |
|   .mjs                  |
+------------------------+
```

---

## Module Responsibilities / 模块职责

### `core/` -- Core Infrastructure / 核心基础设施

#### `patch_base.py` -- Abstract Base Class / 抽象基类

Defines the contract all patches must implement:
定义所有补丁必须实现的契约:

- **`PatchMetadata`** (frozen dataclass) -- Immutable descriptor with `name`, `display_name`, `description`, `version`, `author`, `target_files`, `min_cli_version`, `max_cli_version`, `tags`, `reversible`.
- **`PatchStatus`** (enum) -- `NOT_APPLIED`, `APPLIED`, `FAILED`, `PARTIAL`, `UNKNOWN`.
- **`PatchResult`** (dataclass) -- Mutable operation result with `status`, `message`, `patch_name`, `files_modified`, `backups_created`, `duration_ms`, `error`, `timestamp`.
- **`PatchBase`** (ABC) -- Abstract base with 4 abstract members (`metadata`, `check`, `apply`, `rollback`) and 2 concrete methods (`validate`, `info`).

#### `registry.py` -- Patch Discovery / 补丁发现

Two-layer auto-discovery mechanism:
两层自动发现机制:

1. **Built-in patches** -- Scans `qoder_patchs.patches` package via `pkgutil.iter_modules()`. Modules starting with `_` are excluded.
2. **Third-party patches** -- Discovers via `importlib.metadata.entry_points()` under the `qoder_patchs.patches` group.

#### `engine.py` -- Execution Engine / 执行引擎

Orchestrates patch operations with the following flow:
协调补丁操作, 流程如下:

1. Resolve patch by name from registry
2. Validate pre-conditions (target files exist and are writable)
3. Check if already applied (skip unless `force_reapply`)
4. Delegate to backup manager (if `auto_backup` enabled)
5. Execute the patch's `apply()` or `rollback()` method
6. Collect and return structured `PatchResult`

#### `config.py` -- Configuration Management / 配置管理

Pydantic-based configuration with TOML persistence:
基于 Pydantic 的配置管理, TOML 持久化:

- **`PatchSettings`** -- Backup behavior, dry-run defaults, force-reapply.
- **`UISettings`** -- Theme, banner, verbosity, color.
- **`PathSettings`** -- Bundle directory, backup directory, log file.
- **`PersistenceSettings`** -- Scheduled tasks, npm hooks, auto-repatch.
- **`AppConfig`** -- Root model aggregating all sections, with `load()` and `save()` methods.

Configuration path resolution (`resolve_config_path`):
配置路径解析 (`resolve_config_path`):

```
Priority 1: --config CLI argument
Priority 2: QODER_PATCHS_CONFIG env var
Priority 3: Project root config.toml
Priority 4: User config dir (platformdirs)
Priority 5: Built-in defaults
```

### `cli/` -- CLI Interface / 命令行界面

#### `app.py` -- Typer Application / Typer 应用

Defines the main `typer_app` with commands:
定义主 `typer_app` 及命令:

| Command | Description |
|---------|-------------|
| (default) | Interactive mode with menu loop |
| `apply` | Apply one or all patches |
| `status` | Show patch status (supports `--json`) |
| `rollback` | Rollback a specific patch |
| `config show` | Display current configuration |
| `config set` | Modify a configuration value |
| `about` | Display version and author info |

Global options: `--verbose` / `-v`, `--config` / `-c`.

Application state is managed via a module-level `_state` dictionary with lazy initialization helpers (`_get_config()`, `_get_registry()`, `_get_engine()`, `_get_bundle_dir()`, `_get_cli()`).

#### `menu.py` -- Interactive Menus / 交互式菜单

Questionary-based menus with arrow-key navigation:
基于 Questionary 的菜单, 支持方向键导航:

- `main_menu()` -- Main operation selector.
- `patch_select_menu()` -- Multi-select checkbox for patches.
- `confirm()` -- Yes/no confirmation dialog.
- `config_menu()` -- Interactive configuration editor.

#### `ui.py` -- Output Interface / 输出界面

`BlueCLI` class wrapping Rich Console with:
`BlueCLI` 类封装 Rich Console:

- `banner()` -- ASCII art with blue gradient.
- `success()` / `error()` / `warning()` / `info()` -- Colored status messages.
- `table()` / `status_table()` -- Blue-themed tables.
- `header()` / `divider()` / `heavy_divider()` -- Visual separators.

Module-level helpers (ported from warp.py): `color_text()`, `kv_line()`, `status_dot()`, `divider()`, `heavy_divider()`, `title_line()`, `subtitle_line()`.

#### `theme.py` -- Theme Definitions / 主题定义

- **`BluePalette`** -- 15 color constants (dark navy to ice blue + semantic colors).
- **`BLUE_THEME`** -- Rich `Theme` with 16 style rules.
- **`QUESTIONARY_STYLE`** / `get_questionary_style()` -- prompt_toolkit `Style` for interactive menus.
- **`get_console()`** -- Factory for a UTF-8-safe, blue-themed Rich Console (handles Windows GBK encoding).

#### `charmap.py` -- ASCII Art Engine / ASCII 艺术引擎

- **`CHAR_MAP`** -- Dictionary mapping characters (A-Z, a-z, 0-9, symbols, Unicode) to 6-line-high block glyphs.
- **`BLUE_GRADIENT_PALETTE`** -- 5-stop RGB gradient for banner coloring.
- **`render_text()`** -- Renders text as 6-line ASCII art.
- **`render_gradient_banner()`** -- Applies diagonal ANSI color gradient to rendered art.

### `patches/` -- Patch Implementations / 补丁实现

#### `win10_warning.py` -- Windows 10 Warning Suppression / Win10 警告抑制

Replaces the obfuscated `isWindows10()` function body with `return!1` (i.e., `return false`).
将混淆后的 `isWindows10()` 函数体替换为 `return!1` (即 `return false`).

Two target files: `qodercli.js` and `qoder-worker-runtime.mjs`.

Detection strategies:
1. Export mapping: `isWindows10:()=><NAME>`
2. Fallback call-chain: `<NAME>()&&<var>.push({id:"windows-10"`

Patching strategies:
1. Standard: Replace function body without nested braces.
2. Extended: Handle nested braces by matching to next `function` keyword.

#### `_templates.py` -- Development Templates / 开发模板

Provides `_ExamplePatch` template class, helper functions (`read_file_text`, `create_inline_backup`, `safe_regex_replace`), and a `NEW_PATCH_CHECKLIST`. Excluded from auto-discovery (leading underscore).

### `utils/` -- Utilities / 工具函数

#### `backup.py` -- Backup Manager / 备份管理器

`BackupManager` class with timestamped backup naming (`{name}.bak.{YYYYMMDDHHmmSS}`):
- `create_backup()` -- Create timestamped copy.
- `cleanup_old_backups()` -- Retain only N most recent.
- `restore_from_backup()` -- Restore from specific or latest backup.
- `list_backups()` -- List all backups sorted newest-first.

#### `paths.py` -- Path Resolution / 路径解析

Multi-strategy bundle directory discovery with 6 fallback strategies:
6 种策略定位 bundle 目录:

| Strategy | Method |
|----------|--------|
| A | `config.paths.bundle_dir` |
| B | `QODER_PATCHS_BUNDLE` env var |
| C | `npm prefix -g` |
| D | `APPDATA`-based path |
| E | Common installation paths |
| F | Last-resort filesystem search |

Also provides `get_project_root()` and `get_backup_dir()`.

#### `platform.py` -- Platform Helpers / 平台辅助

- `to_windows_path()` -- MSYS to Windows path conversion (cygpath + pure Python fallback).
- `create_scheduled_task()` / `remove_scheduled_task()` -- Windows scheduled task management via `schtasks.exe`.
- `check_dependencies()` -- Verify npm, node, schtasks.exe availability.
- `is_windows()` -- Platform detection.
- `get_env_safe()` -- Safe environment variable access.

#### `logging.py` -- Logging Configuration / 日志配置

`setup_logging()` configures Loguru with:
- Console handler (colored, INFO or DEBUG level).
- Optional rotating file handler (10 MB rotation, 3-file retention).

---

## Data Flow / 数据流

### Patch Application / 补丁应用

```
User Input
    |
    v
[app.py] apply command or interactive selection
    |
    v
[engine.py] PatchEngine.apply(name, bundle_dir)
    |
    +-- 1. registry.get(name) --> PatchBase instance
    |
    +-- 2. patch.validate(bundle_dir)
    |       --> checks target files exist and are writable
    |
    +-- 3. patch.check(bundle_dir) --> PatchStatus
    |       --> skip if already APPLIED (unless force_reapply)
    |
    +-- 4. backup_manager.create_backup() (if auto_backup)
    |       --> creates timestamped .bak file
    |
    +-- 5. patch.apply(bundle_dir, dry_run)
    |       --> reads target files, detects function name,
    |           performs regex replacement, verifies result
    |
    +-- 6. Returns PatchResult
            --> status, message, files_modified, backups_created,
                duration_ms, error, timestamp
    |
    v
[ui.py] BlueCLI displays success/error with Rich formatting
```

### Patch Discovery / 补丁发现

```
[app.py] _get_registry()
    |
    v
[registry.py] PatchRegistry()
    |
    +-- discover_builtin()
    |       --> pkgutil.iter_modules("qoder_patchs.patches")
    |       --> for each module (skip _private):
    |           --> import module
    |           --> find PatchBase subclasses
    |           --> instantiate and register()
    |
    +-- discover_entry_points("qoder_patchs.patches")
            --> importlib.metadata.entry_points()
            --> for each entry point:
                --> load class
                --> verify PatchBase subclass
                --> instantiate and register()
```

---

## Configuration System / 配置系统

```
+-------------------+     +---------------------+     +-------------------+
| config.toml       |     | config.template.toml |     | Defaults          |
| (user-edited)     |     | (reference)          |     | (Pydantic fields) |
+--------+----------+     +---------------------+     +-------------------+
         |
         v
+-------------------+
| resolve_config_   |
| path()            |
|                   |
| Priority:         |
| 1. --config arg   |
| 2. env var        |
| 3. project root   |
| 4. user config dir|
| 5. None (default) |
+--------+----------+
         |
         v
+-------------------+
| AppConfig.load()  |
|                   |
| tomllib.load()    |
| model_validate()  |
+--------+----------+
         |
         v
+-------------------+
| AppConfig         |
|                   |
| .patch            | --> PatchSettings
| .ui               | --> UISettings
| .paths            | --> PathSettings
| .persistence      | --> PersistenceSettings
+-------------------+
         |
         +---> engine.config (controls behavior)
         +---> cli display (config show)
         +---> interactive editor (config_menu)
```

---

## Extension Points / 扩展点

### 1. Adding a New Patch / 添加新补丁

Create a new module in `patches/` inheriting from `PatchBase`. The registry auto-discovers it via `pkgutil`. See [Patch Development Guide](../patches/guide.md).

### 2. Third-Party Patches via Entry Points / 第三方补丁

External packages can register patches via their own `pyproject.toml`:

```toml
[project.entry-points."qoder_patchs.patches"]
my-external-patch = "my_package.patches:MyExternalPatch"
```

### 3. Custom Themes / 自定义主题

Currently only the "blue" theme is implemented. New themes can be added by:
1. Creating a new palette class (like `BluePalette`).
2. Defining a new Rich `Theme` with style rules.
3. Building a corresponding `QUESTIONARY_STYLE`.
4. Updating `get_console()` and `get_questionary_style()` to select by theme name.

### 4. Configuration Extensions / 配置扩展

Add new settings sections by:
1. Creating a new Pydantic `BaseModel` subclass.
2. Adding it as a field on `AppConfig`.
3. Updating `config_menu()` to include the new section.
4. Adding corresponding TOML entries to `config.template.toml`.
