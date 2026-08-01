"""BlueCLI output wrapper backed by echotools ConsoleUI."""

from __future__ import annotations

from typing import Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cli.echotools_bridge import create_patcher_ui, render_gradient_banner, render_text


class BlueCLI:
    """Terminal output for Patcher; echotools ConsoleUI + Rich markup."""

    def __init__(self, console: Optional[Console] = None) -> None:
        self._ui = create_patcher_ui()
        self.console = console or self._ui._console

    def banner(self, text: str = "QODER") -> None:
        lines = render_text(text)
        print(render_gradient_banner(lines))

    def header(self, title: str) -> None:
        panel = Panel(
            "",
            title=f"[bold bright_blue]{title}[/bold bright_blue]",
            border_style="blue",
            expand=False,
        )
        self.console.print(panel)

    def success(self, msg: str) -> None:
        self.console.print(f"[bold green][OK][/bold green] {msg}")

    def error(self, msg: str) -> None:
        self.console.print(f"[bold red][FAIL][/bold red] {msg}")

    def warning(self, msg: str) -> None:
        self.console.print(f"[bold yellow][!][/bold yellow]  {msg}")

    def info(self, msg: str) -> None:
        self.console.print(f"[bold cyan][i][/bold cyan]  {msg}")

    def table(
        self,
        headers: list[str],
        rows: list[list[str]],
        title: Optional[str] = None,
    ) -> None:
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

    def status_table(self, patches: dict[str, Any]) -> None:
        tbl = Table(
            title="补丁状态",
            show_header=True,
            header_style="bold white on blue",
            border_style="blue",
            title_style="bold bright_blue",
            expand=False,
        )
        tbl.add_column("补丁名称", style="bright_blue")
        tbl.add_column("状态", style="blue")
        labels = {
            "applied": "[bold green]● 已应用[/bold green]",
            "not_applied": "[dim]● 未应用[/dim]",
            "failed": "[bold red]● 失败[/bold red]",
            "partial": "[yellow]● 部分应用[/yellow]",
            "unknown": "[dim yellow]● 未知[/dim yellow]",
        }
        for name, status in patches.items():
            status_val = status.value if hasattr(status, "value") else str(status)
            tbl.add_row(name, labels.get(status_val, f"● {status_val}"))
        self.console.print(tbl)

    def divider(self) -> None:
        self._ui.divider()

    def heavy_divider(self) -> None:
        self._ui.divider(char="═", title="")

    def print(self, *args: Any, **kwargs: Any) -> None:
        self.console.print(*args, **kwargs)

    def newline(self) -> None:
        self.console.print()
