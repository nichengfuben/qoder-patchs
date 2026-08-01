"""Interactive menus for Qoder Patch Manager (echotools-backed)."""

from __future__ import annotations

from typing import Any, Optional

from cli.echotools_bridge import (
    coerce_config_value,
    create_patcher_ui,
    flatten_config_fields,
    run_confirm,
    run_select,
)

MENU_APPLY = "应用补丁"
MENU_STATUS = "查看补丁状态"
MENU_ROLLBACK = "回滚补丁"
MENU_CONFIG = "修改配置"
MENU_ABOUT = "关于"
MENU_EXIT = "退出"
MENU_CANCEL = "返回"

_MAIN_MENU_CHOICES = [
    MENU_APPLY,
    MENU_STATUS,
    MENU_ROLLBACK,
    MENU_CONFIG,
    MENU_ABOUT,
    MENU_EXIT,
]

_menu_ui = None


def _get_menu_ui():
    global _menu_ui
    if _menu_ui is None:
        _menu_ui = create_patcher_ui()
    return _menu_ui


def main_menu() -> str:
    try:
        result = run_select(_get_menu_ui(), "请选择操作:", _MAIN_MENU_CHOICES)
    except (KeyboardInterrupt, EOFError):
        return MENU_EXIT
    if result.index < 0:
        return MENU_EXIT
    return result.value or MENU_EXIT


def patch_select_menu(patches: dict[str, Any]) -> list[str]:
    if not patches:
        return []

    names = list(patches.keys())
    labels: list[str] = []
    values: list[list[str]] = []
    if len(names) > 1:
        labels.append("全部补丁")
        values.append(list(names))
    for name in names:
        patch = patches[name]
        meta = patch.metadata if hasattr(patch, "metadata") else None
        label = f"{meta.display_name} (v{meta.version})" if meta is not None else name
        labels.append(label)
        values.append([name])
    labels.append("取消")
    values.append([])

    try:
        result = run_select(_get_menu_ui(), "选择要操作的补丁:", labels)
    except (KeyboardInterrupt, EOFError):
        return []

    if result.index < 0 or result.index >= len(values):
        return []
    return list(values[result.index])


def confirm(msg: str) -> bool:
    try:
        return run_confirm(_get_menu_ui(), msg, default=True)
    except (KeyboardInterrupt, EOFError):
        return False


def config_menu(config: Any) -> Optional[tuple[str, Any]]:
    ui = _get_menu_ui()
    flat = flatten_config_fields(config)
    if not flat:
        return None

    keys = [k for k, _ in flat]
    labels = [f"{k}  =  {v}" for k, v in flat] + ["← 返回"]
    try:
        result = run_select(ui, "选择要修改的配置项:", labels)
    except (KeyboardInterrupt, EOFError):
        return None

    if result.index < 0 or result.index >= len(keys):
        return None

    selected_key = keys[result.index]
    current_value = dict(flat)[selected_key]
    try:
        new_value_str = ui.input(
            f"输入 {selected_key} 的新值 (当前: {current_value}): ",
        )
    except (KeyboardInterrupt, EOFError):
        return None
    if new_value_str is None:
        return None

    return (selected_key, coerce_config_value(current_value, new_value_str.strip()))
