"""Blue theme definitions for Qoder Patch Manager CLI.

Provides the colour palette, Rich theme, and Questionary style used
throughout the terminal interface.

Classes / constants:
    BluePalette: Colour constants for the blue theme.
    BLUE_THEME: Rich :class:`~rich.theme.Theme` with blue styling rules.
    QUESTIONARY_STYLE: Questionary :class:`~prompt_toolkit.styles.Style`
        for interactive menus.
    get_console: Factory function for a configured :class:`~rich.console.Console`.
"""

from __future__ import annotations

from rich.console import Console
from rich.theme import Theme


# ---------------------------------------------------------------------------
# Blue colour palette
# ---------------------------------------------------------------------------


class BluePalette:
    """Colour constants for the Qoder blue theme.

    All values are hex colour strings suitable for Rich markup.  Colours
    are ordered from darkest to lightest, followed by semantic colours
    for success, warning, error, info, and muted text.
    """

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


# ---------------------------------------------------------------------------
# Rich theme
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Questionary style
# ---------------------------------------------------------------------------

def _build_questionary_style():
    """Build the Questionary Style object lazily.

    Importing ``prompt_toolkit`` at module level can be slow and is not
    needed when running in non-interactive mode.  This helper defers the
    import until the style is actually requested.
    """
    from prompt_toolkit.styles import Style

    return Style(
        [
            ("qmark", "fg:#3b82f6 bold"),
            ("question", "fg:#60a5fa bold"),
            ("answer", "fg:#22c55e bold"),
            ("pointer", "fg:#3b82f6 bold"),
            ("highlighted", "fg:#ffffff bg:#2563eb bold"),
            ("selected", "fg:#93c5fd"),
            ("separator", "fg:#1e3a5f"),
            ("instruction", "fg:#64748b"),
        ]
    )


# Lazily initialised -- call :func:`get_questionary_style` to obtain it.
_QUESTIONARY_STYLE = None


def get_questionary_style():
    """Return the shared Questionary :class:`~prompt_toolkit.styles.Style`.

    The style is built on first call and cached for subsequent calls.
    """
    global _QUESTIONARY_STYLE
    if _QUESTIONARY_STYLE is None:
        _QUESTIONARY_STYLE = _build_questionary_style()
    return _QUESTIONARY_STYLE


# ---------------------------------------------------------------------------
# Console factory
# ---------------------------------------------------------------------------


def _get_utf8_stdout():
    """Return a UTF-8 text stream for stdout on Windows.

    On Chinese Windows the console code page is typically GBK (cp936),
    which cannot encode many Unicode symbols.  Rich
    uses the legacy Win32 console API by default on such systems, which
    writes through the GBK code page and raises ``UnicodeEncodeError``.

    This helper wraps ``sys.stdout.buffer`` in an :class:`io.TextIOWrapper`
    with UTF-8 encoding and ``errors="replace"`` so that any symbol can be
    safely emitted.  On non-Windows platforms the original ``sys.stdout``
    is returned unchanged.
    """
    import io
    import sys

    if sys.platform != "win32":
        return sys.stdout

    try:
        # Wrap the raw binary stdout buffer with a UTF-8 text wrapper.
        # line_buffering=True ensures each line is flushed immediately.
        return io.TextIOWrapper(
            sys.stdout.buffer,
            encoding="utf-8",
            errors="replace",
            line_buffering=True,
        )
    except (AttributeError, OSError):
        # If stdout has no .buffer (e.g. captured in tests), fall back.
        return sys.stdout


def get_console(theme: bool = True) -> Console:
    """Create a :class:`~rich.console.Console` configured with the blue theme.

    On Windows, stdout is wrapped to UTF-8 encoding and Rich's legacy
    Windows rendering is disabled so that Unicode symbols ([i], [OK], [FAIL], [!])
    can be safely emitted without triggering ``UnicodeEncodeError`` on
    GBK-encoded consoles.

    Args:
        theme: If ``True`` (default), apply :data:`BLUE_THEME`.
            If ``False``, return a plain console without theme overrides.

    Returns:
        A new :class:`~rich.console.Console` instance.
    """
    import sys

    kwargs: dict = {}
    if theme:
        kwargs["theme"] = BLUE_THEME

    if sys.platform == "win32":
        # Use UTF-8 wrapped stdout and disable legacy Win32 rendering
        # so Rich emits ANSI escape codes directly.
        kwargs["file"] = _get_utf8_stdout()
        kwargs["force_terminal"] = True

    return Console(**kwargs)
