"""Logging configuration for qoder-patchs.

Provides a single setup function that configures Loguru with colored
console output and an optional rotating file handler.

Functions:
    setup_logging: Configure Loguru handlers for console and optional file output.
"""

from __future__ import annotations

import sys
from typing import Optional

from loguru import logger


# Console format: colored, compact, human-friendly
_CONSOLE_FORMAT = (
    "<blue>{time:HH:mm:ss}</blue> | <level>{level:<8}</level> | {message}"
)

# File format: detailed, machine-parseable, with module/function/line context
_FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | "
    "{name}:{function}:{line} | {message}"
)


def setup_logging(
    verbose: bool = False,
    log_file: Optional[str] = None,
) -> None:
    """Configure Loguru logging for the application.

    Removes all default Loguru handlers and sets up:

    1. **Console handler** -- writes to ``stderr`` with colored output.
       The log level is ``DEBUG`` when ``verbose`` is ``True``, otherwise
       ``INFO``.

    2. **File handler** (optional) -- writes to the specified file path
       with ``DEBUG`` level, 10 MB rotation, and retention of the 3 most
       recent files.  This is useful for unattended runs (e.g., scheduled
       tasks) where console output is not visible.

    Args:
        verbose: If ``True``, set console log level to ``DEBUG``.
            Otherwise, use ``INFO``.
        log_file: Optional file path for a rotating log file.
            Pass ``None`` to disable file logging (console only).

    Example usage::

        setup_logging()  # INFO to console only
        setup_logging(verbose=True)  # DEBUG to console
        setup_logging(log_file="logs/patchs.log")  # INFO console + DEBUG file
        setup_logging(verbose=True, log_file="logs/patchs.log")  # both at DEBUG
    """
    # Remove all existing handlers (Loguru ships with a default stderr handler)
    logger.remove()

    # Console handler: colored output to stderr
    console_level = "DEBUG" if verbose else "INFO"
    logger.add(
        sys.stderr,
        level=console_level,
        format=_CONSOLE_FORMAT,
        colorize=True,
    )

    # File handler: rotating file with detailed format (optional)
    if log_file:
        logger.add(
            log_file,
            level="DEBUG",
            format=_FILE_FORMAT,
            rotation="10 MB",
            retention=3,
            encoding="utf-8",
        )
        logger.debug(f"File logging enabled: {log_file}")

    logger.debug(
        f"Logging configured: console={console_level}, "
        f"file={'enabled' if log_file else 'disabled'}"
    )
