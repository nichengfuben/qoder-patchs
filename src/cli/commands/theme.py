"""Theme helpers for Patcher CLI (echotools-backed, multi-theme)."""

from __future__ import annotations

from echotools.media.console import (
    DEFAULT_THEME_NAME,
    get_console,
    get_gradient_theme,
    get_rich_theme,
    get_theme_palette,
    get_theme_preset,
    list_theme_names,
    normalize_theme_name,
)

__all__ = [
    "DEFAULT_THEME_NAME",
    "get_console",
    "get_gradient_theme",
    "get_rich_theme",
    "get_theme_palette",
    "get_theme_preset",
    "list_theme_names",
    "normalize_theme_name",
]
