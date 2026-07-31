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

from cli import __version__
from cli.commands.config_cmd import config_app

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
    from core.config import AppConfig, resolve_config_path

    if _state["config"] is not None:
        return _state["config"]

    cli_arg = _state.get("config_path")
    config_path = resolve_config_path(cli_arg)
    config = AppConfig.load(config_path)
    _state["config"] = config
    return config


def _get_registry():
    """Lazily create and return the PatchRegistry."""
    from core.registry import PatchRegistry

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
    from core.engine import PatchEngine
    from utils.backup import BackupManager

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

    from utils.paths import find_bundle_dir

    config = _get_config()
    bundle_dir = find_bundle_dir(config)
    _state["bundle_dir"] = bundle_dir
    return bundle_dir


def _get_cli():
    """Lazily create and return BlueCLI."""
    from cli.ui import BlueCLI

    if _state["cli"] is not None:
        return _state["cli"]

    cli = BlueCLI()
    _state["cli"] = cli
    return cli


# ---------------------------------------------------------------------------
# Typer application
# ---------------------------------------------------------------------------

typer_app = typer.Typer(
    name="patcher",
    help="Patcher — Qoder/Cursor CLI 补丁管理工具，交互式菜单与可扩展补丁系统",
    no_args_is_help=False,
    add_completion=True,
    pretty_exceptions_enable=True,
)

typer_app.add_typer(config_app, name="config")


# ---------------------------------------------------------------------------
# Global callback (--verbose, --config)
# ---------------------------------------------------------------------------


@typer_app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="详细输出模式"
    ),
    config: Optional[str] = typer.Option(
        None, "--config", "-c", help="指定配置文件路径"
    ),
) -> None:
    """Qoder CLI 补丁管理工具."""

    # Store global state
    _state["verbose"] = verbose
    _state["config_path"] = config

    # Configure logging
    from utils.logging import setup_logging

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
    from cli.interactive import interactive_mode

    interactive_mode()


def _show_about(cli) -> None:
    """Display about information."""
    from cli.interactive import show_about

    show_about(cli)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def _apply_all(engine, bundle_dir, cli, dry_run: bool) -> None:
    """Apply every registered patch and report a summary."""
    cli.info("应用所有补丁...")
    results = engine.apply_all(bundle_dir, dry_run=dry_run)
    for r in results:
        if r.success:
            cli.success(f"{r.patch_name}: {r.message}")
        else:
            cli.error(f"{r.patch_name}: {r.message}")
    succeeded = sum(1 for r in results if r.success)
    cli.print()
    cli.info(f"完成: {succeeded}/{len(results)} 个补丁应用成功")


def _apply_named(engine, bundle_dir, cli, name: str, dry_run: bool) -> None:
    """Apply a single named patch, exiting with code 1 on failure."""
    cli.info(f"应用补丁: {name}")
    result = engine.apply(name, bundle_dir, dry_run=dry_run)
    if result.success:
        cli.success(f"{result.patch_name}: {result.message}")
    else:
        cli.error(f"{result.patch_name}: {result.message}")
        raise typer.Exit(code=1)


def _apply_interactive_select(engine, bundle_dir, cli, dry_run: bool) -> None:
    """Prompt the user to select patches, then apply each selection."""
    registry = _get_registry()
    config = _get_config()
    from cli.menu import patch_select_menu

    patches = registry.get_all()
    if not patches:
        cli.warning("未找到任何已注册的补丁")
        return

    selected = patch_select_menu(patches)
    if not selected:
        cli.info("未选择任何补丁")
        return

    prev_force = config.patch.force_reapply
    if not dry_run:
        config.patch.force_reapply = True
    try:
        for patch_name in selected:
            result = engine.apply(patch_name, bundle_dir, dry_run=dry_run)
            if result.success:
                cli.success(f"{result.patch_name}: {result.message}")
            else:
                cli.error(f"{result.patch_name}: {result.message}")
    finally:
        config.patch.force_reapply = prev_force


@typer_app.command()
def apply(
    name: Optional[str] = typer.Argument(
        None, help="补丁名称 (省略则进入交互选择)"
    ),
    all_patches: bool = typer.Option(
        False, "--all", "-a", help="应用所有补丁"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-n", help="预览模式 (不修改文件)"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="强制重新应用"
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
            "未找到 Qoder CLI bundle 目录.\n"
            "请在配置中设置 paths.bundle_dir 或设置 PATCHER_BUNDLE（或 AGENTCLI_PATCHS_BUNDLE）环境变量"
        )
        raise typer.Exit(code=10)

    if all_patches:
        _apply_all(engine, bundle_dir, cli, dry_run)
        return

    if name:
        _apply_named(engine, bundle_dir, cli, name, dry_run)
        return

    # No name, no --all -> interactive selection
    _apply_interactive_select(engine, bundle_dir, cli, dry_run)


@typer_app.command()
def status(
    as_json: bool = typer.Option(
        False, "--json", "-j", help="JSON 格式输出 (供脚本消费)"
    ),
) -> None:
    """查看补丁状态."""
    engine = _get_engine()
    bundle_dir = _get_bundle_dir()
    cli = _get_cli()

    if bundle_dir is None:
        cli.warning("未找到 bundle 目录, 无法检查补丁状态")
        # Still show registered patches
        registry = _get_registry()
        names = registry.names()
        if names:
            cli.info(f"已注册补丁: {', '.join(names)}")
        else:
            cli.info("未注册任何补丁")
        raise typer.Exit(code=10)

    statuses = engine.status_all(bundle_dir)

    if as_json:
        data = {k: v.value for k, v in statuses.items()}
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    if not statuses:
        cli.info("未注册任何补丁")
        return

    cli.status_table(statuses)


@typer_app.command()
def rollback(
    name: str = typer.Argument(
        ..., help="要回滚的补丁名称"
    ),
) -> None:
    """回滚补丁."""
    engine = _get_engine()
    bundle_dir = _get_bundle_dir()
    cli = _get_cli()

    if bundle_dir is None:
        cli.error("未找到 bundle 目录")
        raise typer.Exit(code=10)

    cli.info(f"回滚补丁: {name}")
    result = engine.rollback(name, bundle_dir)
    if result.success:
        cli.success(f"{result.patch_name}: {result.message}")
    else:
        cli.error(f"{result.patch_name}: {result.message}")
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# About command
# ---------------------------------------------------------------------------


@typer_app.command()
def about() -> None:
    """关于信息."""
    cli = _get_cli()
    _show_about(cli)
