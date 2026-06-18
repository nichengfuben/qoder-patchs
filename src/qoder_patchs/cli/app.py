"""Typer application and CLI commands for Qoder Patch Manager.

Defines the main :data:`typer_app` Typer application with all user-facing
commands, global options, and interactive menu mode.

Commands:
    (default)   Interactive menu mode with banner and menu loop.
    apply       Apply one or all patches.
    status      Show patch status.
    rollback    Rollback a patch.
    config      Show or modify configuration.
    about       Display about information.

Global options:
    --verbose   Enable verbose/debug output.
    --config    Path to a custom configuration file.

Usage::

    python main.py                     # interactive mode
    python main.py apply --all         # apply all patches
    python main.py status              # show status
    python main.py --help              # show help
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from qoder_patchs import __version__

# ---------------------------------------------------------------------------
# Application-wide state (initialised by the callback)
# ---------------------------------------------------------------------------

_state: dict = {
    "verbose": False,
    "config_path": None,
    "config": None,
    "registry": None,
    "engine": None,
    "backup": None,
    "cli": None,
    "bundle_dir": None,
}


def _get_config():
    """Lazily load and return the AppConfig."""
    from qoder_patchs.core.config import AppConfig, resolve_config_path

    if _state["config"] is not None:
        return _state["config"]

    cli_arg = _state.get("config_path")
    config_path = resolve_config_path(cli_arg)
    config = AppConfig.load(config_path)
    _state["config"] = config
    return config


def _get_registry():
    """Lazily create and return the PatchRegistry."""
    from qoder_patchs.core.registry import PatchRegistry

    if _state["registry"] is not None:
        return _state["registry"]

    registry = PatchRegistry()
    registry.discover_builtin()
    try:
        registry.discover_entry_points()
    except Exception:
        pass
    _state["registry"] = registry
    return registry


def _get_engine():
    """Lazily create and return the PatchEngine."""
    from qoder_patchs.core.engine import PatchEngine
    from qoder_patchs.utils.backup import BackupManager

    if _state["engine"] is not None:
        return _state["engine"]

    config = _get_config()
    registry = _get_registry()
    backup = BackupManager(keep_count=config.patch.backup_count)
    _state["backup"] = backup
    engine = PatchEngine(registry, backup, config)
    _state["engine"] = engine
    return engine


def _get_bundle_dir() -> Optional[Path]:
    """Resolve and cache the bundle directory."""
    if _state["bundle_dir"] is not None:
        return _state["bundle_dir"]

    from qoder_patchs.utils.paths import find_bundle_dir

    config = _get_config()
    bundle_dir = find_bundle_dir(config)
    _state["bundle_dir"] = bundle_dir
    return bundle_dir


def _get_cli():
    """Lazily create and return BlueCLI."""
    from qoder_patchs.cli.ui import BlueCLI

    if _state["cli"] is not None:
        return _state["cli"]

    cli = BlueCLI()
    _state["cli"] = cli
    return cli


# ---------------------------------------------------------------------------
# Typer application
# ---------------------------------------------------------------------------

typer_app = typer.Typer(
    name="qoder-patchs",
    help="Qoder CLI \u8865\u4e01\u7ba1\u7406\u5de5\u5177 -- \u4ea4\u4e92\u5f0f\u83dc\u5355, \u53ef\u6269\u5c55\u8865\u4e01\u7cfb\u7edf",
    # Qoder CLI 补丁管理工具 -- 交互式菜单, 可扩展补丁系统
    no_args_is_help=False,
    add_completion=True,
    pretty_exceptions_enable=True,
)

# Config sub-app
config_app = typer.Typer(
    name="config",
    help="\u914d\u7f6e\u7ba1\u7406",  # 配置管理
)
typer_app.add_typer(config_app, name="config")


# ---------------------------------------------------------------------------
# Global callback (--verbose, --config)
# ---------------------------------------------------------------------------


@typer_app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="\u8be6\u7ec6\u8f93\u51fa\u6a21\u5f0f"  # 详细输出模式
    ),
    config: Optional[str] = typer.Option(
        None, "--config", "-c", help="\u6307\u5b9a\u914d\u7f6e\u6587\u4ef6\u8def\u5f84"  # 指定配置文件路径
    ),
) -> None:
    """Qoder CLI \u8865\u4e01\u7ba1\u7406\u5de5\u5177."""
    # Qoder CLI 补丁管理工具.

    # Store global state
    _state["verbose"] = verbose
    _state["config_path"] = config

    # Configure logging
    from qoder_patchs.utils.logging import setup_logging

    log_file = None
    try:
        cfg = _get_config()
        if cfg.paths.log_file:
            log_file = cfg.paths.log_file
    except Exception:
        pass
    setup_logging(verbose=verbose, log_file=log_file)

    # If a subcommand is being invoked, skip interactive mode
    if ctx.invoked_subcommand is not None:
        return

    # No subcommand -> interactive mode
    _interactive_mode()


# ---------------------------------------------------------------------------
# Interactive mode
# ---------------------------------------------------------------------------


def _interactive_mode() -> None:
    """Run the interactive menu loop."""
    from qoder_patchs.cli.menu import (
        MENU_ABOUT,
        MENU_APPLY,
        MENU_CONFIG,
        MENU_EXIT,
        MENU_ROLLBACK,
        MENU_STATUS,
        main_menu,
    )

    cli = _get_cli()
    config = _get_config()

    # Show banner
    if config.ui.show_banner:
        cli.banner("QODER")
        cli.print()
        cli.print(
            f"  [bold bright_blue]Qoder Patch Manager v{__version__}[/bold bright_blue]"
        )
        cli.divider()
        cli.print()

    # Menu loop
    while True:
        try:
            choice = main_menu()
        except (KeyboardInterrupt, EOFError):
            cli.print()
            cli.info("\u518d\u89c1!")  # 再见!
            break

        if choice == MENU_EXIT:
            cli.info("\u518d\u89c1!")  # 再见!
            break

        elif choice == MENU_APPLY:
            _interactive_apply(cli)

        elif choice == MENU_STATUS:
            _interactive_status(cli)

        elif choice == MENU_ROLLBACK:
            _interactive_rollback(cli)

        elif choice == MENU_CONFIG:
            _interactive_config(cli)

        elif choice == MENU_ABOUT:
            _show_about(cli)

        cli.print()


def _interactive_apply(cli) -> None:
    """Interactive patch application flow."""
    from qoder_patchs.cli.menu import patch_select_menu

    registry = _get_registry()
    engine = _get_engine()
    bundle_dir = _get_bundle_dir()

    patches = registry.get_all()
    if not patches:
        cli.warning("\u672a\u627e\u5230\u4efb\u4f55\u5df2\u6ce8\u518c\u7684\u8865\u4e01")
        # 未找到任何已注册的补丁
        return

    selected = patch_select_menu(patches)
    if not selected:
        cli.info("\u672a\u9009\u62e9\u4efb\u4f55\u8865\u4e01")  # 未选择任何补丁
        return

    if bundle_dir is None:
        cli.error(
            "\u672a\u627e\u5230 Qoder CLI bundle \u76ee\u5f55. "
            "\u8bf7\u5728\u914d\u7f6e\u4e2d\u8bbe\u7f6e paths.bundle_dir"
        )
        # 未找到 Qoder CLI bundle 目录. 请在配置中设置 paths.bundle_dir
        return

    for name in selected:
        cli.info(f"\u6b63\u5728\u5e94\u7528\u8865\u4e01: {name}")  # 正在应用补丁: ...
        result = engine.apply(name, bundle_dir)
        if result.success:
            cli.success(f"{name}: {result.message}")
        else:
            cli.error(f"{name}: {result.message}")


def _interactive_status(cli) -> None:
    """Interactive status display."""
    engine = _get_engine()
    bundle_dir = _get_bundle_dir()

    if bundle_dir is None:
        cli.warning(
            "\u672a\u627e\u5230 bundle \u76ee\u5f55, "
            "\u65e0\u6cd5\u68c0\u67e5\u8865\u4e01\u72b6\u6001"
        )
        # 未找到 bundle 目录, 无法检查补丁状态
        return

    statuses = engine.status_all(bundle_dir)
    if not statuses:
        cli.info("\u672a\u6ce8\u518c\u4efb\u4f55\u8865\u4e01")  # 未注册任何补丁
        return

    cli.status_table(statuses)


def _interactive_rollback(cli) -> None:
    """Interactive rollback flow."""
    from qoder_patchs.cli.menu import confirm as qconfirm
    from qoder_patchs.cli.menu import patch_select_menu

    engine = _get_engine()
    bundle_dir = _get_bundle_dir()
    registry = _get_registry()

    if bundle_dir is None:
        cli.error("\u672a\u627e\u5230 bundle \u76ee\u5f55")
        # 未找到 bundle 目录
        return

    patches = registry.get_all()
    if not patches:
        cli.warning("\u672a\u627e\u5230\u4efb\u4f55\u8865\u4e01")
        # 未找到任何补丁
        return

    selected = patch_select_menu(patches)
    if not selected:
        return

    for name in selected:
        if not qconfirm(f"\u786e\u5b9a\u8981\u56de\u6ede\u8865\u4e01 {name} ?"):
            # 确定要回滚补丁 ... ?
            continue
        result = engine.rollback(name, bundle_dir)
        if result.success:
            cli.success(f"{name}: {result.message}")
        else:
            cli.error(f"{name}: {result.message}")


def _interactive_config(cli) -> None:
    """Interactive config editor."""
    from qoder_patchs.cli.menu import config_menu

    config = _get_config()
    result = config_menu(config)
    if result is None:
        return

    key, new_value = result
    try:
        parts = key.split(".")
        obj = config
        for part in parts[:-1]:
            obj = getattr(obj, part)
        setattr(obj, parts[-1], new_value)

        # Save back
        from qoder_patchs.core.config import resolve_config_path

        config_path = resolve_config_path(_state.get("config_path"))
        if config_path:
            config.save(config_path)
            cli.success(
                f"\u5df2\u66f4\u65b0 {key} = {new_value}"
            )  # 已更新
        else:
            cli.warning(
                "\u914d\u7f6e\u5df2\u4fee\u6539\u4f46\u672a\u627e\u5230\u914d\u7f6e\u6587\u4ef6\u8def\u5f84, "
                "\u66f4\u6539\u4ec5\u5728\u672c\u6b21\u8fd0\u884c\u4e2d\u6709\u6548"
            )
            # 配置已修改但未找到配置文件路径, 更改仅在本次活动有效
    except Exception as exc:
        cli.error(f"\u66f4\u65b0\u5931\u8d25: {exc}")  # 更新失败


def _show_about(cli) -> None:
    """Display about information."""
    cli.print()
    cli.print(f"  [bold bright_blue]Qoder Patch Manager v{__version__}[/bold bright_blue]")
    cli.print("  [dim]\u4f5c\u8005: nichengfuben[/dim]")  # 作者
    cli.print("  [dim]\u8bb8\u53ef\u8bc1: MIT[/dim]")  # 许可证
    cli.print(
        "  [dim]\u63cf\u8ff0: Qoder CLI \u8865\u4e01\u7ba1\u7406\u5de5\u5177, "
        "\u652f\u6301\u4ea4\u4e92\u5f0f\u83dc\u5355\u548c\u53ef\u6269\u5c55\u8865\u4e01\u7cfb\u7edf[/dim]"
    )
    # 描述: Qoder CLI 补丁管理工具, 支持交互式菜单和可扩展补丁系统
    cli.print()


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@typer_app.command()
def apply(
    name: Optional[str] = typer.Argument(
        None, help="\u8865\u4e01\u540d\u79f0 (\u7701\u7565\u5219\u8fdb\u5165\u4ea4\u4e92\u9009\u62e9)"
        # 补丁名称 (省略则进入交互选择)
    ),
    all_patches: bool = typer.Option(
        False, "--all", "-a", help="\u5e94\u7528\u6240\u6709\u8865\u4e01"
        # 应用所有补丁
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-n", help="\u9884\u89c8\u6a21\u5f0f (\u4e0d\u4fee\u6539\u6587\u4ef6)"
        # 预览模式 (不修改文件)
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="\u5f3a\u5236\u91cd\u65b0\u5e94\u7528"
        # 强制重新应用
    ),
) -> None:
    """应用补丁."""
    engine = _get_engine()
    bundle_dir = _get_bundle_dir()
    cli = _get_cli()
    config = _get_config()

    if force:
        config.patch.force_reapply = True

    if bundle_dir is None:
        cli.error(
            "\u672a\u627e\u5230 Qoder CLI bundle \u76ee\u5f55.\n"
            "\u8bf7\u5728\u914d\u7f6e\u4e2d\u8bbe\u7f6e paths.bundle_dir "
            "\u6216\u8bbe\u7f6e QODER_PATCHS_BUNDLE \u73af\u5883\u53d8\u91cf"
        )
        # 未找到 Qoder CLI bundle 目录.
        # 请在配置中设置 paths.bundle_dir 或设置 QODER_PATCHS_BUNDLE 环境变量
        raise typer.Exit(code=10)

    if all_patches:
        cli.info("\u5e94\u7528\u6240\u6709\u8865\u4e01...")  # 应用所有补丁...
        results = engine.apply_all(bundle_dir, dry_run=dry_run)
        for r in results:
            if r.success:
                cli.success(f"{r.patch_name}: {r.message}")
            else:
                cli.error(f"{r.patch_name}: {r.message}")
        succeeded = sum(1 for r in results if r.success)
        cli.print()
        cli.info(
            f"\u5b8c\u6210: {succeeded}/{len(results)} \u4e2a\u8865\u4e01\u5e94\u7528\u6210\u529f"
        )
        # 完成: .../... 个补丁应用成功
        return

    if name:
        cli.info(f"\u5e94\u7528\u8865\u4e01: {name}")  # 应用补丁: ...
        result = engine.apply(name, bundle_dir, dry_run=dry_run)
        if result.success:
            cli.success(f"{result.patch_name}: {result.message}")
        else:
            cli.error(f"{result.patch_name}: {result.message}")
            raise typer.Exit(code=1)
        return

    # No name, no --all -> interactive selection
    registry = _get_registry()
    from qoder_patchs.cli.menu import patch_select_menu

    patches = registry.get_all()
    if not patches:
        cli.warning("\u672a\u627e\u5230\u4efb\u4f55\u5df2\u6ce8\u518c\u7684\u8865\u4e01")
        # 未找到任何已注册的补丁
        return

    selected = patch_select_menu(patches)
    for patch_name in selected:
        result = engine.apply(patch_name, bundle_dir, dry_run=dry_run)
        if result.success:
            cli.success(f"{result.patch_name}: {result.message}")
        else:
            cli.error(f"{result.patch_name}: {result.message}")


@typer_app.command()
def status(
    as_json: bool = typer.Option(
        False, "--json", "-j", help="JSON \u683c\u5f0f\u8f93\u51fa (\u4f9b\u811a\u672c\u6d88\u8d39)"
        # JSON 格式输出 (供脚本消费)
    ),
) -> None:
    """\u67e5\u770b\u8865\u4e01\u72b6\u6001."""  # 查看补丁状态.
    engine = _get_engine()
    bundle_dir = _get_bundle_dir()
    cli = _get_cli()

    if bundle_dir is None:
        cli.warning(
            "\u672a\u627e\u5230 bundle \u76ee\u5f55, "
            "\u65e0\u6cd5\u68c0\u67e5\u8865\u4e01\u72b6\u6001"
        )
        # 未找到 bundle 目录, 无法检查补丁状态
        # Still show registered patches
        registry = _get_registry()
        names = registry.names()
        if names:
            cli.info(
                f"\u5df2\u6ce8\u518c\u8865\u4e01: {', '.join(names)}"
            )  # 已注册补丁
        else:
            cli.info("\u672a\u6ce8\u518c\u4efb\u4f55\u8865\u4e01")  # 未注册任何补丁
        raise typer.Exit(code=10)

    statuses = engine.status_all(bundle_dir)

    if as_json:
        data = {k: v.value for k, v in statuses.items()}
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    if not statuses:
        cli.info("\u672a\u6ce8\u518c\u4efb\u4f55\u8865\u4e01")  # 未注册任何补丁
        return

    cli.status_table(statuses)


@typer_app.command()
def rollback(
    name: str = typer.Argument(
        ..., help="\u8981\u56de\u6ede\u7684\u8865\u4e01\u540d\u79f0"
        # 要回滚的补丁名称
    ),
) -> None:
    """\u56de\u6ede\u8865\u4e01."""  # 回滚补丁.
    engine = _get_engine()
    bundle_dir = _get_bundle_dir()
    cli = _get_cli()

    if bundle_dir is None:
        cli.error("\u672a\u627e\u5230 bundle \u76ee\u5f55")  # 未找到 bundle 目录
        raise typer.Exit(code=10)

    cli.info(f"\u56de\u6ede\u8865\u4e01: {name}")  # 回滚补丁: ...
    result = engine.rollback(name, bundle_dir)
    if result.success:
        cli.success(f"{result.patch_name}: {result.message}")
    else:
        cli.error(f"{result.patch_name}: {result.message}")
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Config sub-commands
# ---------------------------------------------------------------------------


@config_app.command("show")
def config_show() -> None:
    """\u663e\u793a\u5f53\u524d\u914d\u7f6e."""  # 显示当前配置.
    config = _get_config()
    cli = _get_cli()

    cli.print("[bold bright_blue]\u5f53\u524d\u914d\u7f6e:[/bold bright_blue]")
    # 当前配置:

    for section_name in ("patch", "ui", "paths", "persistence"):
        section = getattr(config, section_name, None)
        if section is None:
            continue
        cli.print(f"\n  [bold cyan][{section_name}][/bold cyan]")
        if hasattr(type(section), "model_fields"):
            for field_name in type(section).model_fields:
                value = getattr(section, field_name, None)
                cli.print(f"    {field_name} = {value}")


@config_app.command("set")
def config_set(
    key: str = typer.Argument(
        ..., help="\u914d\u7f6e\u952e (\u652f\u6301\u70b9\u5206\u9694\u8def\u5f84, \u5982 patch.backup_count)"
        # 配置键 (支持点分隔路径, 如 patch.backup_count)
    ),
    value: str = typer.Argument(
        ..., help="\u65b0\u503c"  # 新值
    ),
) -> None:
    """\u4fee\u6539\u914d\u7f6e\u9879."""  # 修改配置项.
    config = _get_config()
    cli = _get_cli()

    try:
        parts = key.split(".")
        obj = config
        for part in parts[:-1]:
            obj = getattr(obj, part)

        # Type coercion
        current = getattr(obj, parts[-1], None)
        if isinstance(current, bool):
            new_value: object = value.lower() in ("true", "1", "yes", "\u662f")
        elif isinstance(current, int):
            new_value = int(value)
        elif current is None and value in ("None", "null", ""):
            new_value = None
        else:
            new_value = value

        setattr(obj, parts[-1], new_value)

        # Save
        from qoder_patchs.core.config import resolve_config_path

        config_path = resolve_config_path(_state.get("config_path"))
        if config_path:
            config.save(config_path)
            cli.success(f"\u5df2\u66f4\u65b0 {key} = {new_value}")  # 已更新
        else:
            cli.warning(
                "\u672a\u627e\u5230\u914d\u7f6e\u6587\u4ef6, "
                "\u66f4\u6539\u4ec5\u5728\u672c\u6b21\u8fd0\u884c\u4e2d\u6709\u6548"
            )
            # 未找到配置文件, 更改仅在本次活动有效
    except (AttributeError, ValueError) as exc:
        cli.error(f"\u914d\u7f6e\u66f4\u65b0\u5931\u8d25: {exc}")  # 配置更新失败
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# About command
# ---------------------------------------------------------------------------


@typer_app.command()
def about() -> None:
    """\u5173\u4e8e\u4fe1\u606f."""  # 关于信息.
    cli = _get_cli()
    _show_about(cli)
