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

from qoder_patchs.cli.theme import get_questionary_style


# Menu option constants (Chinese labels)
MENU_APPLY = "\u5e94\u7528\u8865\u4e01"             # 应用补丁
MENU_STATUS = "\u67e5\u770b\u8865\u4e01\u72b6\u6001"  # 查看补丁状态
MENU_ROLLBACK = "\u56de\u6ede\u8865\u4e01"           # 回滚补丁
MENU_CONFIG = "\u4fee\u6539\u914d\u7f6e"             # 修改配置
MENU_ABOUT = "\u5173\u4e8e"                          # 关于
MENU_EXIT = "\u9000\u51fa"                            # 退出
MENU_CANCEL = "\u8fd4\u56de"                          # 返回

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
            "\u8bf7\u9009\u62e9\u64cd\u4f5c:",  # 请选择操作:
            choices=_MAIN_MENU_CHOICES,
            style=style,
            instruction="(\u4f7f\u7528\u65b9\u5411\u952e\u9009\u62e9, Enter \u786e\u8ba4)",
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
            "\u9009\u62e9\u8981\u5e94\u7528\u7684\u8865\u4e01:",
            # 选择要应用的补丁:
            choices=choices,
            style=style,
            instruction=(
                "(\u4f7f\u7528\u65b9\u5411\u952e\u9009\u62e9, "
                "\u7a7a\u683c\u5207\u6362\u591a\u9009, "
                "Enter \u786e\u8ba4)"
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


def config_menu(config: Any) -> Optional[tuple[str, Any]]:
    """Interactive configuration editor.

    Displays all configurable keys with their current values and lets the
    user pick one to edit.  The new value is entered via a text input.

    Args:
        config: An :class:`~qoder_patchs.core.config.AppConfig` instance.

    Returns:
        A ``(key, new_value)`` tuple if the user edited a setting, or
        ``None`` if the user cancelled.
    """
    style = get_questionary_style()

    # Flatten config into dot-path key/value pairs
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

    if not flat:
        return None

    # Let the user pick a key
    choices = [
        questionary.Choice(
            title=f"{key}  =  {value}",
            value=key,
        )
        for key, value in flat
    ]
    choices.append(questionary.Choice(title="\u2190 \u8fd4\u56de", value="__back__"))
    # ← 返回

    try:
        selected_key = questionary.select(
            "\u9009\u62e9\u8981\u4fee\u6539\u7684\u914d\u7f6e\u9879:",
            # 选择要修改的配置项:
            choices=choices,
            style=style,
        ).ask()
    except (KeyboardInterrupt, EOFError):
        selected_key = None

    if selected_key is None or selected_key == "__back__":
        return None

    # Find the current value
    current_value = ""
    for key, value in flat:
        if key == selected_key:
            current_value = value
            break

    # Prompt for new value
    try:
        new_value_str = questionary.text(
            f"\u8f93\u5165 {selected_key} \u7684\u65b0\u503c "
            f"(\u5f53\u524d: {current_value}):",
            # 输入 ... 的新值 (当前: ...):
            style=style,
            default=current_value,
        ).ask()
    except (KeyboardInterrupt, EOFError):
        new_value_str = None

    if new_value_str is None:
        return None

    # Type coercion: booleans
    if current_value in ("True", "False"):
        new_value: Any = new_value_str.lower() in ("true", "1", "yes", "\u662f")
    elif current_value.isdigit():
        try:
            new_value = int(new_value_str)
        except ValueError:
            new_value = new_value_str
    elif current_value == "None":
        new_value = None if new_value_str in ("", "None", "null") else new_value_str
    else:
        new_value = new_value_str

    return (selected_key, new_value)
