"""Blue theme re-exports for Patcher CLI (echotools-backed)."""

from __future__ import annotations

from rich.console import Console
from rich.theme import Theme

from cli.echotools_bridge import _get_utf8_stdout, _PATCHER_THEME


class BluePalette:
    DARK_NAVY: str = "#0a1628"
    NAVY: str = "#1a2744"
    DEEP_BLUE: str = "#1e3a5f"
    BLUE: str = "#2563eb"
    BRIGHT_BLUE: str = "#3b82f6"
    LIGHT_BLUE: str = "#60a5fa"
    SKY: str = "#93c5fd"
    ICE_BLUE: str = "#bfdbfe"
    WHITE_BLUE: str = "#dbeafe"
    SUCCESS: str = "#22c55e"
    WARNING: str = "#eab308"
    ERROR: str = "#ef4444"
    INFO: str = "#06b6d4"
    MUTED: str = "#64748b"


BLUE_THEME = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "bold red",
        "success": "bold green",
        "header": "bold bright_blue",
        "header.title": "bold blue on dark_blue",
        "menu.selected": "bold white on blue",
        "menu.unselected": "dim blue",
        "prompt": "bold cyan",
        "accent": "bright_blue",
        "muted": "dim blue",
        "border": "blue",
        "table.header": "bold white on blue",
        "table.row": "blue",
        "table.footer": "bold bright_blue",
    }
)


def get_console(theme: bool = True) -> Console:
    import sys

    kwargs: dict = {}
    if theme:
        kwargs["theme"] = BLUE_THEME
    if sys.platform == "win32" and "pytest" not in sys.modules:
        kwargs["file"] = _get_utf8_stdout()
        kwargs["force_terminal"] = True
    return Console(**kwargs)


def get_patcher_gradient_theme():
    return _PATCHER_THEME
