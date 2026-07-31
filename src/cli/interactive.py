"""Interactive menu mode implementation for the Qoder Patch Manager CLI.

Contains the interactive menu loop and its per-menu-item handlers. Split
out of :mod:`cli.app` to keep that module within the project's
per-file line limit.
"""

from __future__ import annotations

from cli import __version__


def _show_interactive_banner(cli, config) -> None:
    """Print the startup banner and title block if enabled in config."""
    if not config.ui.show_banner:
        return
    cli.banner("PATCHER")
    cli.print()
    cli.print(
        f"  [bold bright_blue]Patcher v{__version__}[/bold bright_blue]"
    )
    cli.divider()
    cli.print()


def _dispatch_menu_choice(choice: str, cli) -> bool:
    """Handle a single main-menu selection.

    Returns:
        ``True`` if the menu loop should exit.
    """
    from cli.menu import (
        MENU_ABOUT,
        MENU_APPLY,
        MENU_CONFIG,
        MENU_EXIT,
        MENU_ROLLBACK,
        MENU_STATUS,
    )

    if choice == MENU_EXIT:
        cli.info("再见!")  # 再见!
        return True

    handlers = {
        MENU_APPLY: _interactive_apply,
        MENU_STATUS: _interactive_status,
        MENU_ROLLBACK: _interactive_rollback,
        MENU_CONFIG: _interactive_config,
        MENU_ABOUT: show_about,
    }
    handler = handlers.get(choice)
    if handler is not None:
        handler(cli)
    return False


def interactive_mode() -> None:
    """Run the interactive menu loop."""
    from cli import app
    from cli.menu import main_menu

    cli = app._get_cli()
    config = app._get_config()

    _show_interactive_banner(cli, config)

    while True:
        try:
            choice = main_menu()
        except (KeyboardInterrupt, EOFError):
            cli.print()
            cli.info("再见!")  # 再见!
            break

        if _dispatch_menu_choice(choice, cli):
            break

        cli.print()


def _interactive_apply(cli) -> None:
    """Interactive patch application flow."""
    from cli import app
    from cli.menu import patch_select_menu

    registry = app._get_registry()
    engine = app._get_engine()
    config = app._get_config()
    bundle_dir = app._get_bundle_dir()

    patches = registry.get_all()
    if not patches:
        cli.warning("未找到任何已注册的补丁")
        # 未找到任何已注册的补丁
        return

    selected = patch_select_menu(patches)
    if not selected:
        cli.info("未选择任何补丁")  # 未选择任何补丁
        return

    if bundle_dir is None:
        cli.error(
            "未找到 Qoder CLI bundle 目录. "
            "请在配置中设置 paths.bundle_dir"
        )
        # 未找到 Qoder CLI bundle 目录. 请在配置中设置 paths.bundle_dir
        return

    # 菜单里主动选中即视为要重打（否则已 APPLIED 会被引擎直接跳过）
    prev_force = config.patch.force_reapply
    config.patch.force_reapply = True
    try:
        for name in selected:
            cli.info(f"正在应用补丁: {name}")  # 正在应用补丁: ...
            result = engine.apply(name, bundle_dir)
            if result.success:
                cli.success(f"{name}: {result.message}")
            else:
                cli.error(f"{name}: {result.message}")
    finally:
        config.patch.force_reapply = prev_force


def _interactive_status(cli) -> None:
    """Interactive status display."""
    from cli import app

    engine = app._get_engine()
    bundle_dir = app._get_bundle_dir()

    if bundle_dir is None:
        cli.warning(
            "未找到 bundle 目录, "
            "无法检查补丁状态"
        )
        # 未找到 bundle 目录, 无法检查补丁状态
        return

    statuses = engine.status_all(bundle_dir)
    if not statuses:
        cli.info("未注册任何补丁")  # 未注册任何补丁
        return

    cli.status_table(statuses)


def _interactive_rollback(cli) -> None:
    """Interactive rollback flow."""
    from cli import app
    from cli.menu import confirm as qconfirm
    from cli.menu import patch_select_menu

    engine = app._get_engine()
    bundle_dir = app._get_bundle_dir()
    registry = app._get_registry()

    if bundle_dir is None:
        cli.error("未找到 bundle 目录")
        # 未找到 bundle 目录
        return

    patches = registry.get_all()
    if not patches:
        cli.warning("未找到任何补丁")
        # 未找到任何补丁
        return

    selected = patch_select_menu(patches)
    if not selected:
        cli.info("未选择任何补丁")
        return

    for name in selected:
        if not qconfirm(f"确定要回滞补丁 {name} ?"):
            # 确定要回滚补丁 ... ?
            continue
        result = engine.rollback(name, bundle_dir)
        if result.success:
            cli.success(f"{name}: {result.message}")
        else:
            cli.error(f"{name}: {result.message}")


def _interactive_config(cli) -> None:
    """Interactive config editor."""
    from cli import app
    from cli.menu import config_menu

    config = app._get_config()
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
        from core.config import resolve_config_path

        config_path = resolve_config_path(app._state.get("config_path"))
        if config_path:
            config.save(config_path)
            cli.success(
                f"已更新 {key} = {new_value}"
            )  # 已更新
        else:
            cli.warning(
                "配置已修改但未找到配置文件路径, "
                "更改仅在本次运行中有效"
            )
            # 配置已修改但未找到配置文件路径, 更改仅在本次活动有效
    except Exception as exc:
        cli.error(f"更新失败: {exc}")  # 更新失败


def show_about(cli) -> None:
    """Display about information."""
    cli.print()
    cli.print(f"  [bold bright_blue]AgentCLI Patchs v{__version__}[/bold bright_blue]")
    cli.print("  [dim]作者: nichengfuben[/dim]")  # 作者
    cli.print("  [dim]许可证: MIT[/dim]")  # 许可证
    cli.print(
        "  [dim]描述: Qoder CLI 补丁管理工具, "
        "支持交互式菜单和可扩展补丁系统[/dim]"
    )
    # 描述: Qoder CLI 补丁管理工具, 支持交互式菜单和可扩展补丁系统
    cli.print()
