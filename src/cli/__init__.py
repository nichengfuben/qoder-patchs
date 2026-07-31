"""CLI interface for Patcher.

Provides Typer-based command-line interface with:
- Interactive menus (Questionary)
- Blue theme (Rich)
- ASCII art banner (charmap)
"""

__version__ = "2.4.3"

from cli.app import typer_app
from cli.charmap import (
    BLUE_GRADIENT_PALETTE,
    render_gradient_banner,
    render_text,
)
from cli.commands.theme import (
    BLUE_THEME,
    BluePalette,
    get_console,
    get_questionary_style,
)
from cli.ui import BlueCLI

__all__ = [
    "BLUE_GRADIENT_PALETTE",
    "BLUE_THEME",
    "BlueCLI",
    "BluePalette",
    "__version__",
    "get_console",
    "get_questionary_style",
    "render_gradient_banner",
    "render_text",
    "typer_app",
]
