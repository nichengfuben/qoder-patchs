"""CLI interface for Qoder Patch Manager.

Provides Typer-based command-line interface with:
- Interactive menus (Questionary)
- Blue theme (Rich)
- ASCII art banner (charmap)
"""

from qoder_patchs.cli.app import typer_app
from qoder_patchs.cli.charmap import (
    BLUE_GRADIENT_PALETTE,
    render_gradient_banner,
    render_text,
)
from qoder_patchs.cli.theme import (
    BLUE_THEME,
    BluePalette,
    get_console,
    get_questionary_style,
)
from qoder_patchs.cli.ui import BlueCLI

__all__ = [
    "BLUE_GRADIENT_PALETTE",
    "BLUE_THEME",
    "BlueCLI",
    "BluePalette",
    "get_console",
    "get_questionary_style",
    "render_gradient_banner",
    "render_text",
    "typer_app",
]
