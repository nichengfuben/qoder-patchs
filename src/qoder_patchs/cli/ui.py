"""BlueCLI output wrapper for Qoder Patch Manager.

Provides the :class:`BlueCLI` class that wraps :class:`rich.console.Console`
with blue-themed panels, tables, banners, status messages, and dividers.
Also ports several lightweight terminal UI helpers from warp.py.

Classes:
    BlueCLI: High-level terminal output interface with blue theming.

Functions (module-level helpers ported from warp.py ``UI`` class):
    color_text: Apply an ANSI colour to a string.
    kv_line: Format a key-value pair for terminal display.
    status_dot: Render a coloured status circle.
    divider / heavy_divider: Thin / thick horizontal rule.
    title_line / subtitle_line: Styled title strings.
"""

from __future__ import annotations

import sys
from typing import Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from qoder_patchs.cli.charmap import (
    BLUE_GRADIENT_PALETTE,
    render_gradient_banner,
    render_text,
)
from qoder_patchs.cli.theme import get_console


# ---------------------------------------------------------------------------
# ANSI colour helpers (ported from warp.py UI class)
# ---------------------------------------------------------------------------

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[97m"


def _color_ok() -> bool:
    """Return ``True`` if the terminal appears to support ANSI colours."""
    try:
        return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    except Exception:
        return False


def color_text(color: str, text: str) -> str:
    """Wrap *text* in the given ANSI *color* code, respecting ``isatty``."""
    if not _color_ok():
        return text
    return f"{color}{text}{RESET}"


def kv_line(key: str, value: str, kw: int = 20) -> str:
    """Format a key-value pair with the key in cyan, padded to *kw* width."""
    return f"    {color_text(CYAN, key.ljust(kw))}{value}"


def status_dot(status: str) -> str:
    """Return a coloured circle marker for the given *status* string.

    Recognises ``active`` / ``running`` (green), ``inactive`` / ``dead`` /
    ``failed`` (red), and anything else (yellow).
    """
    if status in ("active", "running", "applied"):
        return color_text(GREEN, f"\u25cf {status}")
    if status in ("inactive", "dead", "failed", "not_applied"):
        return color_text(RED, f"\u25cf {status}")
    return color_text(YELLOW, f"\u25cf {status}")


def divider(width: int = 55) -> str:
    """Thin horizontal rule (``\\u2500``)."""
    return color_text(DIM, "  " + "\u2500" * width)


def heavy_divider(width: int = 55) -> str:
    """Thick horizontal rule (``\\u2550``) in cyan."""
    return color_text(CYAN, "  " + "\u2550" * width)


def title_line(text: str) -> str:
    """Bold white title string."""
    return color_text(BOLD + WHITE, f"\n  {text}")


def subtitle_line(text: str) -> str:
    """Dim white subtitle string."""
    return color_text(DIM + WHITE, f"  {text}")


# ---------------------------------------------------------------------------
# BlueCLI class
# ---------------------------------------------------------------------------


class BlueCLI:
    """High-level terminal output interface with blue theming.

    Wraps a :class:`rich.console.Console` and provides convenience methods
    for headers, success/error/warning/info messages, tables, banners,
    dividers, and patch status display.

    Args:
        console: An optional pre-configured :class:`~rich.console.Console`.
            If ``None``, one is created via :func:`~qoder_patchs.cli.theme.get_console`.

    Example usage::

        cli = BlueCLI()
        cli.banner("QODER")
        cli.header("Patch Manager")
        cli.success("All patches applied!")
        cli.status_table({"win10-warning": PatchStatus.APPLIED})
    """

    def __init__(self, console: Optional[Console] = None) -> None:
        self.console = console or get_console(theme=True)

    # ---- Banner / ASCII art -----------------------------------------------

    def banner(self, text: str = "QODER") -> None:
        """Print an ASCII art banner with a blue diagonal gradient.

        Args:
            text: The text to render (default ``"QODER"``).
        """
        lines = render_text(text)
        rendered = render_gradient_banner(lines, list(BLUE_GRADIENT_PALETTE))
        # Print directly (not through Rich) to preserve raw ANSI escapes
        print(rendered)

    # ---- Header / Panel ---------------------------------------------------

    def header(self, title: str) -> None:
        """Print a blue-bordered panel with the given *title*.

        Args:
            title: Panel title text.
        """
        panel = Panel(
            "",
            title=f"[bold bright_blue]{title}[/bold bright_blue]",
            border_style="blue",
            expand=False,
        )
        self.console.print(panel)

    # ---- Status messages --------------------------------------------------

    def success(self, msg: str) -> None:
        """Print a green success message.

        Args:
            msg: Message text.
        """
        self.console.print(f"[bold green][OK][/bold green] {msg}")

    def error(self, msg: str) -> None:
        """Print a red error message.

        Args:
            msg: Message text.
        """
        self.console.print(f"[bold red][FAIL][/bold red] {msg}")

    def warning(self, msg: str) -> None:
        """Print a yellow warning message.

        Args:
            msg: Message text.
        """
        self.console.print(f"[bold yellow][!][/bold yellow]  {msg}")

    def info(self, msg: str) -> None:
        """Print a cyan informational message.

        Args:
            msg: Message text.
        """
        self.console.print(f"[bold cyan][i][/bold cyan]  {msg}")

    # ---- Table ------------------------------------------------------------

    def table(
        self,
        headers: list[str],
        rows: list[list[str]],
        title: Optional[str] = None,
    ) -> None:
        """Print a blue-themed table.

        Args:
            headers: Column header strings.
            rows: List of row data (each row is a list of cell strings).
            title: Optional table title.
        """
        tbl = Table(
            title=title,
            show_header=True,
            header_style="bold white on blue",
            border_style="blue",
            title_style="bold bright_blue",
            expand=False,
        )
        for h in headers:
            tbl.add_column(h, style="blue")
        for row in rows:
            tbl.add_row(*row)
        self.console.print(tbl)

    # ---- Patch status table -----------------------------------------------

    def status_table(self, patches: dict[str, Any]) -> None:
        """Print a table of patch statuses.

        Args:
            patches: A dict mapping patch names to
                :class:`~qoder_patchs.core.patch_base.PatchStatus` enums
                or plain status strings.
        """
        tbl = Table(
            title="\u8865\u4e01\u72b6\u6001",  # 补丁状态
            show_header=True,
            header_style="bold white on blue",
            border_style="blue",
            title_style="bold bright_blue",
            expand=False,
        )
        tbl.add_column("\u8865\u4e01\u540d\u79f0", style="bright_blue")  # 补丁名称
        tbl.add_column("\u72b6\u6001", style="blue")  # 状态

        _STATUS_LABELS = {
            "applied": "[bold green]\u25cf \u5df2\u5e94\u7528[/bold green]",
            "not_applied": "[dim]\u25cf \u672a\u5e94\u7528[/dim]",
            "failed": "[bold red]\u25cf \u5931\u8d25[/bold red]",
            "partial": "[yellow]\u25cf \u90e8\u5206\u5e94\u7528[/yellow]",
            "unknown": "[dim yellow]\u25cf \u672a\u77e5[/dim yellow]",
        }

        for name, status in patches.items():
            status_val = status.value if hasattr(status, "value") else str(status)
            label = _STATUS_LABELS.get(status_val, f"\u25cf {status_val}")
            tbl.add_row(name, label)

        self.console.print(tbl)

    # ---- Dividers ---------------------------------------------------------

    def divider(self) -> None:
        """Print a thin divider line."""
        print(divider())

    def heavy_divider(self) -> None:
        """Print a thick cyan divider line."""
        print(heavy_divider())

    # ---- Misc -------------------------------------------------------------

    def print(self, *args: Any, **kwargs: Any) -> None:
        """Proxy to the underlying Rich console's ``print`` method."""
        self.console.print(*args, **kwargs)

    def newline(self) -> None:
        """Print a blank line."""
        self.console.print()
