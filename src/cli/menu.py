"""Interactive menus for Qoder Patch Manager.

Provides Questionary-based interactive menus with arrow-key navigation,
multi-select checkboxes, and yes/no confirmation dialogs.  All menus
handle ``KeyboardInterrupt`` (Ctrl+C) gracefully by returning a sentinel
value indicating the user cancelled.

Functions:
    main_menu: Display the main operation menu.
    patch_select_menu: Multi-select patches for application.
    confirm: Yes/no confirmation prompt.
    config_menu: Interactive configuration editor.
"""

from __future__ import annotations

from typing import Any, Optional

import questionary

from cli.commands.theme import get_questionary_style


# Menu option constants (Chinese labels)
MENU_APPLY = "应用补丁"             # 应用补丁
MENU_STATUS = "查看补丁状态"  # 查看补丁状态
MENU_ROLLBACK = "回滞补丁"           # 回滚补丁
MENU_CONFIG = "修改配置"             # 修改配置
MENU_ABOUT = "关于"                          # 关于
MENU_EXIT = "退出"                            # 退出
MENU_CANCEL = "返回"                          # 返回

_MAIN_MENU_CHOICES = [
    MENU_APPLY,
    MENU_STATUS,
    MENU_ROLLBACK,
    MENU_CONFIG,
    MENU_ABOUT,
    MENU_EXIT,
]


def main_menu() -> str:
    """Display the main menu and return the selected option.

    Uses Questionary's ``select`` widget with arrow-key navigation.
    Returns :data:`MENU_EXIT` if the user presses Ctrl+C.

    Returns:
        The selected menu option string (one of the ``MENU_*`` constants).
    """
    style = get_questionary_style()
    try:
        answer = questionary.select(
            "请选择操作:",  # 请选择操作:
            choices=_MAIN_MENU_CHOICES,
            style=style,
            instruction="(使用方向键选择, Enter 确认)",
            # 使用方向键选择, Enter 确认
        ).ask()
    except (KeyboardInterrupt, EOFError):
        answer = None

    if answer is None:
        return MENU_EXIT
    return answer


def patch_select_menu(patches: dict[str, Any]) -> list[str]:
    """Display a multi-select checkbox of available patches.

    Each patch is shown with its display name and version.  The user can
    toggle individual patches with Space and confirm with Enter.

    Args:
        patches: A dict mapping patch names to :class:`PatchBase` instances
            (or any object with a ``metadata`` attribute exposing
            ``display_name`` and ``version``).

    Returns:
        A list of selected patch name strings.  Returns an empty list if
        the user cancels (Ctrl+C) or selects nothing.
    """
    if not patches:
        return []

    style = get_questionary_style()

    # Build choices: display label -> internal name
    choices: list[questionary.Choice] = []
    for name, patch in patches.items():
        meta = patch.metadata if hasattr(patch, "metadata") else None
        if meta is not None:
            label = f"{meta.display_name} (v{meta.version})"
        else:
            label = name
        choices.append(questionary.Choice(title=label, value=name))

    try:
        answer = questionary.checkbox(
            "选择要应用的补丁:",
            # 选择要应用的补丁:
            choices=choices,
            style=style,
            instruction=(
                "(使用方向键选择, "
                "空格切换多选, "
                "Enter 确认)"
            ),
            # 使用方向键选择, 空格切换多选, Enter 确认
        ).ask()
    except (KeyboardInterrupt, EOFError):
        answer = None

    if answer is None:
        return []
    return answer


def confirm(msg: str) -> bool:
    """Prompt the user for yes/no confirmation.

    Args:
        msg: The confirmation question to display.

    Returns:
        ``True`` if the user answered yes, ``False`` otherwise (including
        Ctrl+C cancellation).
    """
    style = get_questionary_style()
    try:
        answer = questionary.confirm(
            msg,
            style=style,
            default=True,
        ).ask()
    except (KeyboardInterrupt, EOFError):
        answer = None

    return bool(answer)


def _flatten_config_fields(config: Any) -> list[tuple[str, str]]:
    """Flatten config into dot-path key/value pairs.

    Args:
        config: An :class:`~core.config.AppConfig` instance.

    Returns:
        A list of ``(dot_path, str_value)`` tuples for every field in
        the ``patch``, ``ui``, ``paths`` and ``persistence`` sections.
    """
    flat: list[tuple[str, str]] = []
    for section_name in ("patch", "ui", "paths", "persistence"):
        section = getattr(config, section_name, None)
        if section is None:
            continue
        if hasattr(type(section), "model_fields"):
            fields = type(section).model_fields
        elif hasattr(section, "__fields__"):
            fields = section.__fields__
        else:
            continue
        for field_name in fields:
            dot_path = f"{section_name}.{field_name}"
            current = getattr(section, field_name, None)
            flat.append((dot_path, str(current)))
    return flat


def _prompt_config_key(flat: list[tuple[str, str]], style: Any) -> Optional[str]:
    """Prompt the user to pick a config key to edit.

    Args:
        flat: The flattened ``(dot_path, str_value)`` pairs.
        style: The Questionary style to apply.

    Returns:
        The selected dot-path key, or ``None`` if the user cancelled or
        chose the "back" option.
    """
    choices = [
        questionary.Choice(
            title=f"{key}  =  {value}",
            value=key,
        )
        for key, value in flat
    ]
    choices.append(questionary.Choice(title="← 返回", value="__back__"))
    # ← 返回

    try:
        selected_key = questionary.select(
            "选择要修改的配置项:",
            # 选择要修改的配置项:
            choices=choices,
            style=style,
        ).ask()
    except (KeyboardInterrupt, EOFError):
        selected_key = None

    if selected_key is None or selected_key == "__back__":
        return None
    return selected_key


def _prompt_new_value(selected_key: str, current_value: str, style: Any) -> Optional[str]:
    """Prompt the user for a new raw string value.

    Args:
        selected_key: The dot-path key being edited.
        current_value: The current string value of that key.
        style: The Questionary style to apply.

    Returns:
        The new raw string value entered by the user, or ``None`` if
        cancelled.
    """
    try:
        new_value_str = questionary.text(
            f"输入 {selected_key} 的新值 "
            f"(当前: {current_value}):",
            # 输入 ... 的新值 (当前: ...):
            style=style,
            default=current_value,
        ).ask()
    except (KeyboardInterrupt, EOFError):
        new_value_str = None

    return new_value_str


def _coerce_config_value(current_value: str, new_value_str: str) -> Any:
    """Coerce a raw new-value string to match the current value's type.

    Args:
        current_value: The current string value (used to infer type).
        new_value_str: The raw new value entered by the user.

    Returns:
        The coerced value (``bool``, ``int``, ``None`` or ``str``).
    """
    if current_value in ("True", "False"):
        new_value: Any = new_value_str.lower() in ("true", "1", "yes", "是")
    elif current_value.isdigit():
        try:
            new_value = int(new_value_str)
        except ValueError:
            new_value = new_value_str
    elif current_value == "None":
        new_value = None if new_value_str in ("", "None", "null") else new_value_str
    else:
        new_value = new_value_str
    return new_value


def config_menu(config: Any) -> Optional[tuple[str, Any]]:
    """Interactive configuration editor.

    Displays all configurable keys with their current values and lets the
    user pick one to edit.  The new value is entered via a text input.

    Args:
        config: An :class:`~core.config.AppConfig` instance.

    Returns:
        A ``(key, new_value)`` tuple if the user edited a setting, or
        ``None`` if the user cancelled.
    """
    style = get_questionary_style()

    flat = _flatten_config_fields(config)
    if not flat:
        return None

    selected_key = _prompt_config_key(flat, style)
    if selected_key is None:
        return None

    # Find the current value
    current_value = ""
    for key, value in flat:
        if key == selected_key:
            current_value = value
            break

    new_value_str = _prompt_new_value(selected_key, current_value, style)
    if new_value_str is None:
        return None

    new_value = _coerce_config_value(current_value, new_value_str)
    return (selected_key, new_value)
