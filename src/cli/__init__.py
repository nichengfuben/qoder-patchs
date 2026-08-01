"""CLI interface for Patcher.

Typer commands + echotools ConsoleUI interactive menus.
"""

__version__ = "2.4.5"

from cli.app import typer_app
from cli.commands.theme import BLUE_THEME, BluePalette, get_console, get_patcher_gradient_theme
from cli.echotools_bridge import (
    BLUE_GRADIENT_PALETTE,
    render_gradient_banner,
    render_text,
)
from cli.ui import BlueCLI

__all__ = [
    "BLUE_GRADIENT_PALETTE",
    "BLUE_THEME",
    "BlueCLI",
    "BluePalette",
    "__version__",
    "get_console",
    "get_patcher_gradient_theme",
    "render_gradient_banner",
    "render_text",
    "typer_app",
]
