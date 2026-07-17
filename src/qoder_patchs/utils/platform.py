"""Cross-platform helper utilities for qoder-patchs.

Provides Windows-specific path conversion, scheduled task management,
dependency checking, and safe environment variable access. These helpers
replace the Bash/MSYS workarounds from the original shell scripts.

Functions:
    to_windows_path: Convert MSYS/Git Bash paths to Windows paths.
    create_scheduled_task: Create a Windows scheduled task.
    remove_scheduled_task: Remove a Windows scheduled task.
    check_dependencies: Check runtime dependency availability.
    is_windows: Check if running on Windows.
    get_env_safe: Safely read an environment variable.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

from loguru import logger


def to_windows_path(msys_path: str) -> str:
    """Convert an MSYS/Git Bash path to a native Windows path.

    Attempts two strategies in order:

    1. **cygpath** -- If available (Git Bash environment), delegates to
       ``cygpath -w`` for accurate conversion.
    2. **Pure Python fallback** -- Parses the ``/x/...`` MSYS path format
       and converts it to ``X:\\...`` Windows format.

    Args:
        msys_path: An MSYS-style path (e.g., ``/c/Users/alice/file.sh``).

    Returns:
        The equivalent Windows path (e.g., ``C:\\Users\\alice\\file.sh``).
        Returns the original string unchanged if conversion is not possible.

    Example::

        >>> to_windows_path("/c/Users/alice/script.sh")
        'C:\\\\Users\\\\alice\\\\script.sh'
    """
    win_path = _to_windows_path_via_cygpath(msys_path)
    if win_path is not None:
        return win_path

    win_path = _to_windows_path_via_regex(msys_path)
    if win_path is not None:
        return win_path

    # Already a Windows path or unrecognized format
    logger.debug(f"Path not convertible, returning as-is: {msys_path}")
    return msys_path


def _to_windows_path_via_cygpath(msys_path: str) -> str | None:
    """Attempt MSYS-to-Windows path conversion via ``cygpath -w``.

    Returns:
        The converted path, or ``None`` if ``cygpath`` is unavailable or
        the conversion failed.
    """
    cygpath_exe = shutil.which("cygpath")
    if not cygpath_exe:
        return None

    try:
        result = subprocess.run(
            ["cygpath", "-w", msys_path],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            win_path = result.stdout.strip()
            logger.debug(f"cygpath converted: {msys_path} -> {win_path}")
            return win_path
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.debug(f"cygpath failed for '{msys_path}': {exc}")

    return None


def _to_windows_path_via_regex(msys_path: str) -> str | None:
    """Attempt MSYS-to-Windows path conversion via a pure Python regex.

    Matches the ``/x/...`` MSYS path format where ``x`` is a single
    drive letter.

    Returns:
        The converted path, or ``None`` if ``msys_path`` does not match
        the expected MSYS format.
    """
    match = re.match(r"^/([a-zA-Z])/(.*)", msys_path)
    if not match:
        return None

    drive_letter = match.group(1).upper()
    rest = match.group(2).replace("/", "\\")
    win_path = f"{drive_letter}:\\{rest}"
    logger.debug(f"Python converted: {msys_path} -> {win_path}")
    return win_path


def create_scheduled_task(task_name: str, script_path: str) -> bool:
    """Create a Windows scheduled task that runs a script at user logon.

    Uses ``schtasks.exe`` to create the task. If a task with the same
    name already exists, it is deleted and recreated. All paths are
    converted to Windows format before being passed to ``schtasks.exe``.

    Args:
        task_name: The scheduled task name (e.g., ``"QoderPatchAutoApply"``).
        script_path: Path to the script to execute. Can be an MSYS-style
            path; it will be converted automatically.

    Returns:
        ``True`` if the task was created successfully, ``False`` otherwise.

    Note:
        This function is Windows-only. On non-Windows platforms, it
        logs a warning and returns ``False``.
    """
    if not is_windows():
        logger.warning("Scheduled tasks are only supported on Windows")
        return False

    schtasks_exe = shutil.which("schtasks.exe")
    if not schtasks_exe:
        logger.error("schtasks.exe not found on PATH")
        return False

    win_bash, win_script = _resolve_scheduled_task_paths(task_name, script_path)

    _delete_existing_scheduled_task(task_name)

    return _create_scheduled_task_entry(task_name, win_bash, win_script)


def _resolve_scheduled_task_paths(task_name: str, script_path: str) -> tuple[str, str]:
    """Resolve and log the Windows-format bash and script paths for a task."""
    # Resolve bash.exe for the task command
    bash_exe = shutil.which("bash") or "bash"
    win_bash = to_windows_path(bash_exe)
    win_script = to_windows_path(script_path)

    logger.debug(f"Creating scheduled task: {task_name}")
    logger.debug(f"  bash: {win_bash}")
    logger.debug(f"  script: {win_script}")

    return win_bash, win_script


def _delete_existing_scheduled_task(task_name: str) -> None:
    """Delete an existing scheduled task, ignoring errors if it doesn't exist."""
    try:
        subprocess.run(
            ["schtasks.exe", "/delete", "/tn", task_name, "/f"],
            capture_output=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.debug(f"Delete existing task failed (may not exist): {exc}")


def _create_scheduled_task_entry(task_name: str, win_bash: str, win_script: str) -> bool:
    """Invoke ``schtasks.exe /create`` for the given task and command.

    Returns:
        ``True`` if the task was created successfully, ``False`` otherwise.
    """
    try:
        result = subprocess.run(
            [
                "schtasks.exe", "/create",
                "/tn", task_name,
                "/tr", f'"{win_bash}" "{win_script}"',
                "/sc", "ONLOGON",
                "/f",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            logger.info(f"Scheduled task created successfully: {task_name}")
            return True

        stderr = result.stderr.strip() if result.stderr else "unknown error"
        logger.error(f"schtasks.exe /create failed (rc={result.returncode}): {stderr}")
        return False

    except subprocess.TimeoutExpired:
        logger.error("schtasks.exe /create timed out")
        return False
    except OSError as exc:
        logger.error(f"schtasks.exe /create error: {exc}")
        return False


def remove_scheduled_task(task_name: str) -> bool:
    """Remove a Windows scheduled task.

    Args:
        task_name: The scheduled task name to remove.

    Returns:
        ``True`` if the task was removed successfully, ``False`` otherwise.

    Note:
        This function is Windows-only. On non-Windows platforms, it
        logs a warning and returns ``False``.
    """
    if not is_windows():
        logger.warning("Scheduled tasks are only supported on Windows")
        return False

    schtasks_exe = shutil.which("schtasks.exe")
    if not schtasks_exe:
        logger.error("schtasks.exe not found on PATH")
        return False

    logger.debug(f"Removing scheduled task: {task_name}")

    try:
        result = subprocess.run(
            ["schtasks.exe", "/delete", "/tn", task_name, "/f"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            logger.info(f"Scheduled task removed successfully: {task_name}")
            return True

        stderr = result.stderr.strip() if result.stderr else "unknown error"
        logger.error(f"schtasks.exe /delete failed (rc={result.returncode}): {stderr}")
        return False

    except subprocess.TimeoutExpired:
        logger.error("schtasks.exe /delete timed out")
        return False
    except OSError as exc:
        logger.error(f"schtasks.exe /delete error: {exc}")
        return False


def check_dependencies() -> list[tuple[str, bool, str]]:
    """Check all runtime dependencies required by qoder-patchs.

    Verifies the availability of each dependency on the system ``PATH``
    and returns a list of check results.

    Checked dependencies:
        - **npm**: Required to locate the Qoder CLI bundle directory
          via ``npm prefix -g``.
        - **node**: Required as the npm runtime environment.
        - **schtasks.exe**: Required for Windows scheduled task creation
          (Windows only, optional on other platforms).

    Returns:
        A list of ``(name, available, description)`` tuples. ``available``
        is ``True`` if the dependency was found on ``PATH``.

    Example::

        results = check_dependencies()
        for name, available, desc in results:
            status = "OK" if available else "MISSING"
            print(f"  {name}: {status} -- {desc}")
    """
    checks: list[tuple[str, bool, str]] = []

    checks.append(_check_npm_dependency())
    checks.append(_check_node_dependency())

    schtasks_check = _check_schtasks_dependency()
    if schtasks_check is not None:
        checks.append(schtasks_check)

    _log_dependency_summary(checks)

    return checks


def _check_npm_dependency() -> tuple[str, bool, str]:
    """Check for npm, used to find the bundle directory via npm prefix -g."""
    npm_path = shutil.which("npm")
    return (
        "npm",
        npm_path is not None,
        "Used to locate the Qoder CLI bundle directory (npm prefix -g)",
    )


def _check_node_dependency() -> tuple[str, bool, str]:
    """Check for node, npm's runtime."""
    node_path = shutil.which("node")
    return (
        "node",
        node_path is not None,
        "Required by npm as the JavaScript runtime",
    )


def _check_schtasks_dependency() -> tuple[str, bool, str] | None:
    """Check for schtasks.exe, only relevant on Windows.

    Returns:
        The check tuple, or ``None`` if not running on Windows.
    """
    if not is_windows():
        return None

    schtasks_path = shutil.which("schtasks.exe")
    return (
        "schtasks.exe",
        schtasks_path is not None,
        "Used to create on-logon scheduled tasks for auto-patching",
    )


def _log_dependency_summary(checks: list[tuple[str, bool, str]]) -> None:
    """Log a summary of how many dependencies were found available."""
    available_count = sum(1 for _, avail, _ in checks if avail)
    total_count = len(checks)
    logger.debug(f"Dependency check: {available_count}/{total_count} available")


def is_windows() -> bool:
    """Check if the current platform is Windows.

    Returns:
        ``True`` if running on Windows (``sys.platform == "win32"``).
    """
    return sys.platform == "win32"


def get_env_safe(name: str, default: str = "") -> str:
    """Safely read an environment variable with a default fallback.

    Unlike :func:`os.environ.get`, this function also handles the case
    where the value exists but is an empty string, returning the default
    in that case as well.

    Args:
        name: The environment variable name (e.g., ``"APPDATA"``).
        default: Value to return if the variable is not set or is empty.
            Defaults to ``""``.

    Returns:
        The environment variable value, or ``default`` if not set or empty.

    Example::

        >>> get_env_safe("APPDATA")
        'C:\\\\Users\\\\alice\\\\AppData\\\\Roaming'
        >>> get_env_safe("NONEXISTENT_VAR", "fallback")
        'fallback'
    """
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value
