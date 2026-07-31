"""Detection/patching helpers for the Windows 10 warning suppression patch.

Split out of :mod:`patches.win10_warning` to keep that module
within the project's per-file line limit. Pure functions only, no I/O.
"""

from __future__ import annotations

import re
from typing import Optional

from loguru import logger

# ---------------------------------------------------------------------------
# Compiled regex patterns (replace ``grep -oP`` invocations from the Bash version)
# ---------------------------------------------------------------------------

# Strategy 1: standard export mapping, e.g. ``isWindows10:()=>t2``
EXPORT_PATTERN = re.compile(r"isWindows10:\(\)=>(\w+)")

# Strategy 2: fallback call-chain, e.g. ``t2()&&warnings.push({id:"windows-10"``
FALLBACK_PATTERN = re.compile(r'(\w+)\(\)&&\w+\.push\(\{id:"windows-10"')

# Detection of an already-patched function, e.g. ``function t2(){return!1}``
PATCHED_PATTERN = re.compile(r"function (\w+)\(\)\{return!1\}")


def detect_func_name(content: str, fname: str) -> Optional[str]:
    """Detect the obfuscated function name mapped to ``isWindows10``.

    Two detection strategies are tried in order:

    1. **Export mapping** -- looks for ``isWindows10:()=><NAME>``.
    2. **Fallback call-chain** -- looks for ``<NAME>()&&<var>.push({id:"windows-10"``.

    Args:
        content: Full text content of the target file.
        fname: File name (for logging purposes).

    Returns:
        The detected function name, or ``None`` if neither strategy matches.
    """
    match = EXPORT_PATTERN.search(content)
    if match:
        logger.debug(
            "Detected function name via export mapping in {}: {}",
            fname,
            match.group(1),
        )
        return match.group(1)

    match = FALLBACK_PATTERN.search(content)
    if match:
        logger.debug(
            "Detected function name via fallback call-chain in {}: {}",
            fname,
            match.group(1),
        )
        return match.group(1)

    return None


def do_patch(content: str, func_name: str) -> Optional[str]:
    """Replace the function body with ``return!1``.

    Two replacement strategies are attempted:

    1. **Standard** -- ``function <name>(){...}`` where the body has no
       nested braces.
    2. **Extended** -- handles bodies with nested braces by matching up to
       the next ``function`` keyword.

    Args:
        content: Full text content of the target file.
        func_name: The obfuscated function name to patch.

    Returns:
        The patched content string, or ``None`` if neither strategy
        produced a verifiable result.
    """
    escaped = re.escape(func_name)

    result = re.sub(
        rf"function {escaped}\(\)\{{[^}}]*\}}",
        f"function {func_name}(){{return!1}}",
        content,
    )
    if verify_patch(result, func_name):
        logger.debug("Patch applied via standard strategy for {}", func_name)
        return result

    result = re.sub(
        rf"function {escaped}\(\)\{{.*?\}}function",
        f"function {func_name}(){{return!1}}function",
        content,
    )
    if verify_patch(result, func_name):
        logger.debug("Patch applied via extended strategy for {}", func_name)
        return result

    logger.error("Neither patching strategy succeeded for {}", func_name)
    return None


def verify_patch(content: str, func_name: str) -> bool:
    """Verify that the patched function body is present in *content*.

    Args:
        content: Text content to verify.
        func_name: The function name that should now return ``!1``.

    Returns:
        ``True`` if the expected replacement is found.
    """
    return bool(
        re.search(
            rf"function {re.escape(func_name)}\(\)\{{return!1\}}",
            content,
        )
    )
