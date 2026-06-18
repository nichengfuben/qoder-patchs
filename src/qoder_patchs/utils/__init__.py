"""Utility functions for Qoder Patch Manager.

Re-exports key utilities from submodules for convenient access:

- :class:`BackupManager` -- file backup lifecycle management
- :func:`setup_logging` -- Loguru configuration
- :func:`find_bundle_dir` -- multi-strategy bundle directory discovery
- :func:`get_project_root` -- project root resolution
- :func:`get_backup_dir` -- backup directory resolution
- :func:`to_windows_path` -- MSYS to Windows path conversion
- :func:`create_scheduled_task` -- Windows scheduled task creation
- :func:`remove_scheduled_task` -- Windows scheduled task removal
- :func:`check_dependencies` -- runtime dependency checking
- :func:`is_windows` -- platform detection
- :func:`get_env_safe` -- safe environment variable access
"""

from qoder_patchs.utils.backup import BackupManager
from qoder_patchs.utils.logging import setup_logging
from qoder_patchs.utils.paths import find_bundle_dir, get_backup_dir, get_project_root
from qoder_patchs.utils.platform import (
    check_dependencies,
    create_scheduled_task,
    get_env_safe,
    is_windows,
    remove_scheduled_task,
    to_windows_path,
)

__all__ = [
    # Backup
    "BackupManager",
    # Logging
    "setup_logging",
    # Paths
    "find_bundle_dir",
    "get_backup_dir",
    "get_project_root",
    # Platform
    "check_dependencies",
    "create_scheduled_task",
    "get_env_safe",
    "is_windows",
    "remove_scheduled_task",
    "to_windows_path",
]
