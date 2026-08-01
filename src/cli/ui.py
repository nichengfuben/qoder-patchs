"""Patcher CLI output: RichCLI + patch-specific widgets."""

from __future__ import annotations

from typing import Any, Optional

from echotools.media.console import RichCLI, normalize_theme_name
from rich.table import Table


class PatcherCLI(RichCLI):
    """Rich CLI with Patcher-specific status table."""

    def __init__(self, theme_name: str | None = None, console=None) -> None:
        super().__init__(theme_name=normalize_theme_name(theme_name), console=console)

    def status_table(self, patches: dict[str, Any]) -> None:
        preset = self._preset
        tbl = Table(
            title="补丁状态",
            show_header=True,
            header_style=f"bold white on {preset.border}",
            border_style=preset.border,
            title_style=preset.header,
            expand=False,
        )
        tbl.add_column("补丁名称", style=preset.accent)
        tbl.add_column("状态", style=preset.column)
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
