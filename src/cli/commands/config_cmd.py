"""Config sub-commands (`agentcli-patchs config show|set`).

Split out of :mod:`cli.app` to keep that module within the
project's per-file line limit.
"""

from __future__ import annotations

import typer

config_app = typer.Typer(
    name="config",
    help="配置管理",  # 配置管理
)


@config_app.command("show")
def config_show() -> None:
    """显示当前配置."""  # 显示当前配置.
    from cli import app

    config = app._get_config()
    cli = app._get_cli()

    cli.print("[header]当前配置:[/header]")
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
        ..., help="配置键 (支持点分隔路径, 如 patch.backup_count)"
        # 配置键 (支持点分隔路径, 如 patch.backup_count)
    ),
    value: str = typer.Argument(
        ..., help="新值"  # 新值
    ),
) -> None:
    """修改配置项."""  # 修改配置项.
    from cli import app
    from echotools.media.console import coerce_config_set_value

    config = app._get_config()
    cli = app._get_cli()

    try:
        parts = key.split(".")
        obj = config
        for part in parts[:-1]:
            obj = getattr(obj, part)

        current = getattr(obj, parts[-1], None)
        new_value = coerce_config_set_value(current, value)
        setattr(obj, parts[-1], new_value)

        from core.config import resolve_config_path

        config_path = resolve_config_path(app._state.get("config_path"))
        if config_path:
            config.save(config_path)
            cli.success(f"已更新 {key} = {new_value}")  # 已更新
        else:
            cli.warning(
                "未找到配置文件, "
                "更改仅在本次运行中有效"
            )
            # 未找到配置文件, 更改仅在本次活动有效
    except (AttributeError, ValueError) as exc:
        cli.error(f"配置更新失败: {exc}")  # 配置更新失败
        raise typer.Exit(code=1)
