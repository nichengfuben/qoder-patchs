"""Sync bridge to echotools.media.console for Patcher CLI."""

from __future__ import annotations

import asyncio
import io
import sys
from typing import Any, List, Optional, Sequence, Tuple

from echotools.media.console import GradientTheme, TextUtils, char_map, create_ui
from echotools.media.console.uicore.ui_platform import _get_backend
from echotools.media.console.uicore.ui_text import GradientRenderer
from echotools.media.console.uiwidgets.ui_select import SelectionResult

BLUE_GRADIENT_PALETTE: List[Tuple[int, int, int]] = [
    (20, 80, 255),
    (40, 120, 255),
    (60, 160, 255),
    (80, 200, 255),
    (100, 230, 255),
]

_PATCHER_THEME = GradientTheme(
    primary_start=(37, 99, 235),
    primary_end=(96, 165, 250),
    border_start=(30, 58, 95),
    border_end=(37, 99, 235),
    accent_start=(59, 130, 246),
    accent_end=(147, 197, 253),
    success=(34, 197, 94),
    warning=(234, 179, 8),
    error=(239, 68, 68),
    info=(6, 182, 212),
    muted=(100, 116, 139),
)


def _ensure_windows_console() -> None:
    if sys.platform != "win32":
        return
    try:
        _get_backend().init_console()
    except Exception:
        pass


def _get_utf8_stdout():
    if sys.platform != "win32":
        return sys.stdout
    if "pytest" in sys.modules:
        return sys.stdout
    try:
        return io.TextIOWrapper(
            sys.stdout.buffer,
            encoding="utf-8",
            errors="replace",
            line_buffering=True,
        )
    except (AttributeError, OSError):
        return sys.stdout


def create_patcher_ui(*, normal_mode: bool = False):
    _ensure_windows_console()
    ui = create_ui(theme=_PATCHER_THEME, char_map=char_map, normal_mode=normal_mode)
    if sys.platform == "win32" and not normal_mode and "pytest" not in sys.modules:
        ui._console.file = _get_utf8_stdout()  # type: ignore[attr-defined]
        ui._console._force_terminal = True  # type: ignore[attr-defined]
    return ui


def run_select(ui, title: str, options: Sequence[str], default_index: int = 0) -> SelectionResult:
    return asyncio.run(ui.select(title, list(options), default_index))


def run_confirm(ui, message: str, default: bool = True) -> bool:
    return asyncio.run(ui.confirm(message, default))


def render_text(text: str) -> list[str]:
    lines = ["", "", "", "", "", ""]
    for ch in text:
        glyph = char_map.get(ch) or char_map.get(ch.upper()) or char_map.get(ch.lower())
        if glyph is not None:
            for i in range(6):
                lines[i] += glyph[i]
    return lines


def render_gradient_banner(
    lines: list[str],
    palette: Optional[List[Tuple[int, int, int]]] = None,
) -> str:
    if not lines:
        return ""
    theme = _PATCHER_THEME
    if palette:
        theme = GradientTheme(
            primary_start=palette[0],
            primary_end=palette[-1],
            border_start=palette[0],
            border_end=palette[-1],
        )
    renderer = GradientRenderer(theme)
    banner = renderer.render_banner("\n".join(lines), use_border_colors=True, row_offset=0)
    return str(banner)


def flatten_config_fields(config: Any) -> list[tuple[str, str]]:
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
    return flat


def coerce_config_value(current_value: str, new_value_str: str) -> Any:
    if current_value in ("True", "False"):
        return new_value_str.lower() in ("true", "1", "yes", "是")
    if current_value.isdigit():
        try:
            return int(new_value_str)
        except ValueError:
            return new_value_str
    if current_value == "None":
        return None if new_value_str in ("", "None", "null") else new_value_str
    return new_value_str


def coerce_config_set_value(current: object, value: str) -> object:
    if isinstance(current, bool):
        return value.lower() in ("true", "1", "yes", "是")
    if isinstance(current, int):
        return int(value)
    if current is None and value in ("None", "null", ""):
        return None
    return value


def render_bar(pct: Any, width: int = 30) -> str:
    try:
        p = max(0.0, min(100.0, float(pct)))
    except Exception:
        return "[" + ("░" * width) + "]"
    filled = int(width * p / 100.0)
    return "[" + ("█" * filled) + ("░" * (width - filled)) + "]"


def truncate_ansi(text: str, width: int) -> str:
    if TextUtils.display_width(text) <= width:
        return text
    plain = TextUtils.strip_ansi(text)
    trimmed = TextUtils.truncate(plain, max(0, width - 1))
    return trimmed + "…\033[0m"
