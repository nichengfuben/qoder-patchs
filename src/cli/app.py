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
    """Resolve and cache the Qoder CLI bundle directory."""
    if _state["bundle_dir"] is not None:
        return _state["bundle_dir"]

    from utils.paths import find_bundle_dir

    config = _get_config()
    bundle_dir = find_bundle_dir(config)
    _state["bundle_dir"] = bundle_dir
    return bundle_dir


def _target_dir_for_patch(name: str) -> Optional[Path]:
    """按补丁解析目标目录：cursor-agent 用 Agent 安装根，其余用 Qoder bundle。"""
    if name == "cursor-agent":
        from sc.core.paths import find_cursor_agent_bundle

        return find_cursor_agent_bundle()
    return _get_bundle_dir()


def _missing_target_hint(name: str) -> str:
    if name == "cursor-agent":
        return (
            "未找到 Cursor Agent（versions/*/index.js）。\n"
            "Linux/macOS: ~/.local/share/cursor-agent；"
            "Windows: %LOCALAPPDATA%\\cursor-agent"
        )
    return (
        "未找到 Qoder CLI bundle 目录。\n"
        "请设置 paths.bundle_dir 或 PATCHER_BUNDLE / AGENTCLI_PATCHS_BUNDLE"
    )


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


def _apply_one(engine, cli, name: str, dry_run: bool) -> bool:
    """Resolve target for *name*, apply, report. Return success."""
    target = _target_dir_for_patch(name)
    if target is None:
        cli.error(f"{name}: {_missing_target_hint(name)}")
        return False
    cli.info(f"应用补丁: {name}")
    result = engine.apply(name, target, dry_run=dry_run)
    if result.success:
        cli.success(f"{result.patch_name}: {result.message}")
        return True
    cli.error(f"{result.patch_name}: {result.message}")
    return False


def _apply_all(engine, cli, dry_run: bool) -> None:
    """Apply every registered patch (each with its own target dir)."""
    cli.info("应用所有补丁...")
    names = _get_registry().names()
    results = [_apply_one(engine, cli, n, dry_run) for n in names]
    succeeded = sum(1 for ok in results if ok)
    cli.print()
    cli.info(f"完成: {succeeded}/{len(results)} 个补丁应用成功")


def _apply_interactive_select(engine, cli, dry_run: bool) -> None:
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
            _apply_one(engine, cli, patch_name, dry_run)
    finally:
        config.patch.force_reapply = prev_force


def _collect_statuses(engine) -> dict:
    """Per-patch status using the correct target directory for each."""
    from core.patch_base import PatchStatus

    out = {}
    for name in _get_registry().names():
        target = _target_dir_for_patch(name)
        if target is None:
            out[name] = PatchStatus.UNKNOWN
            continue
        out[name] = engine.status(name, target)
    return out


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
    cli = _get_cli()
    config = _get_config()

    if force:
        config.patch.force_reapply = True

    if all_patches:
        _apply_all(engine, cli, dry_run)
        return

    if name:
        if not _apply_one(engine, cli, name, dry_run):
            raise typer.Exit(code=1)
        return

    _apply_interactive_select(engine, cli, dry_run)


@typer_app.command()
def status(
    as_json: bool = typer.Option(
        False, "--json", "-j", help="JSON 格式输出 (供脚本消费)"
    ),
) -> None:
    """查看补丁状态."""
    engine = _get_engine()
    cli = _get_cli()
    statuses = _collect_statuses(engine)

    if as_json:
        data = {k: v.value for k, v in statuses.items()}
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    if not statuses:
        cli.info("未注册任何补丁")
        return

    for name, st in statuses.items():
        if st.value == "unknown" and _target_dir_for_patch(name) is None:
            cli.warning(f"{name}: {_missing_target_hint(name)}")
    cli.status_table(statuses)


@typer_app.command()
def rollback(
    name: str = typer.Argument(
        ..., help="要回滚的补丁名称"
    ),
) -> None:
    """回滚补丁."""
    engine = _get_engine()
    cli = _get_cli()
    target = _target_dir_for_patch(name)
    if target is None:
        cli.error(_missing_target_hint(name))
        raise typer.Exit(code=10)

    cli.info(f"回滚补丁: {name}")
    result = engine.rollback(name, target)
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
