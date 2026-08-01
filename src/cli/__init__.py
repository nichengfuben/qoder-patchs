"""CLI interface for Patcher.

Typer commands + echotools ConsoleUI interactive menus.
"""

__version__ = "2.5.3"

from cli.app import typer_app
from cli.commands.theme import (
    DEFAULT_THEME_NAME,
    get_console,
    get_gradient_theme,
    list_theme_names,
    normalize_theme_name,
)
from cli.ui import PatcherCLI
from echotools.media.console import render_gradient_banner, render_text

__all__ = [
    "DEFAULT_THEME_NAME",
    "PatcherCLI",
    "__version__",
    "get_console",
    "get_gradient_theme",
    "list_theme_names",
    "normalize_theme_name",
    "render_gradient_banner",
    "render_text",
    "typer_app",
]
