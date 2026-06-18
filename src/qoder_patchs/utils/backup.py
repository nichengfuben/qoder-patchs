"""Backup management for qoder-patchs.

Provides file backup creation, cleanup, and restoration with timestamped
backup naming. Backups are stored alongside the original files using the
naming convention ``{original_name}.bak.{YYYYMMDDHHmmSS}``.

Classes:
    BackupManager: Manages file backup lifecycle operations.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Optional

from loguru import logger


class BackupManager:
    """Manages file backup creation, cleanup, and restoration.

    Backups are created alongside the original file with a timestamped
    suffix, allowing multiple backup versions to coexist. The manager
    supports retention policies to limit the number of backups kept.

    Backup naming convention::

        original_file.js.bak.20250618143022

    Args:
        keep_count: Default number of backups to retain during cleanup.
            Must be between 1 and 10. Defaults to ``3``.

    Example usage::

        bm = BackupManager(keep_count=3)
        backup_path = bm.create_backup(Path("bundle/qodercli.js"))
        bm.cleanup_old_backups(Path("bundle/qodercli.js"))
        restored = bm.restore_from_backup(Path("bundle/qodercli.js"))
    """

    def __init__(self, keep_count: int = 3) -> None:
        """Initialize the backup manager.

        Args:
            keep_count: Default number of backups to retain (1-10).
        """
        self._keep_count = max(1, min(10, keep_count))

    @property
    def keep_count(self) -> int:
        """The default number of backups to retain."""
        return self._keep_count

    def create_backup(self, file_path: Path) -> Path:
        """Create a timestamped backup copy of a file.

        The backup is placed alongside the original file with the naming
        convention ``{name}.bak.{YYYYMMDDHHmmSS}``. The timestamp is
        generated at the time of the call.

        Args:
            file_path: Path to the file to back up.

        Returns:
            Path to the newly created backup file.

        Raises:
            FileNotFoundError: If ``file_path`` does not exist.
            PermissionError: If the file or directory is not writable.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Cannot backup non-existent file: {file_path}")

        timestamp = time.strftime("%Y%m%d%H%M%S")
        backup_name = f"{file_path.name}.bak.{timestamp}"
        backup_path = file_path.parent / backup_name

        # Avoid name collisions if called within the same second
        if backup_path.exists():
            suffix = 1
            while backup_path.exists():
                backup_name = f"{file_path.name}.bak.{timestamp}_{suffix}"
                backup_path = file_path.parent / backup_name
                suffix += 1

        shutil.copy2(str(file_path), str(backup_path))
        # Explicitly set mtime to current time (copy2 preserves source mtime,
        # which would make all backups share the same timestamp)
        now = time.time()
        os.utime(str(backup_path), (now, now))
        logger.debug(f"Backup created: {backup_path}")
        return backup_path

    def cleanup_old_backups(self, file_path: Path, keep: Optional[int] = None) -> None:
        """Remove old backups, keeping only the most recent N.

        Backups are identified by the ``{file_name}.bak.*`` glob pattern
        in the same directory as ``file_path``. They are sorted by
        modification time (newest first), and any beyond the ``keep``
        threshold are deleted.

        Args:
            file_path: Path to the original file (used to derive the
                backup glob pattern).
            keep: Number of backups to retain. Defaults to
                :attr:`keep_count` if not specified.
        """
        if keep is None:
            keep = self._keep_count

        backups = self.list_backups(file_path)

        if len(backups) <= keep:
            logger.debug(
                f"Backup count ({len(backups)}) within limit ({keep}), no cleanup needed"
            )
            return

        to_remove = backups[keep:]
        for backup in to_remove:
            try:
                backup.unlink()
                logger.debug(f"Removed old backup: {backup}")
            except OSError as exc:
                logger.warning(f"Failed to remove old backup {backup}: {exc}")

        logger.info(
            f"Cleanup complete for {file_path.name}: "
            f"removed {len(to_remove)} backups, kept {keep}"
        )

    def restore_from_backup(
        self,
        file_path: Path,
        backup_path: Optional[Path] = None,
    ) -> Optional[Path]:
        """Restore a file from a backup.

        If ``backup_path`` is provided, restores from that specific backup.
        Otherwise, automatically selects the most recent backup based on
        modification time.

        The original file (if it exists) is overwritten with the backup
        contents. If the original file does not exist, it is created.

        Args:
            file_path: Path to the file to restore (the original location).
            backup_path: Optional specific backup file to restore from.
                If ``None``, the latest backup is used.

        Returns:
            Path to the backup file used for restoration, or ``None`` if
            no suitable backup was found.
        """
        if backup_path is not None:
            if not backup_path.exists():
                logger.error(f"Specified backup does not exist: {backup_path}")
                return None
            selected = backup_path
        else:
            backups = self.list_backups(file_path)
            if not backups:
                logger.warning(f"No backups found for: {file_path}")
                return None
            selected = backups[0]  # Most recent (list is sorted descending)

        try:
            shutil.copy2(str(selected), str(file_path))
            logger.info(f"Restored {file_path} from backup: {selected}")
            return selected
        except OSError as exc:
            logger.error(f"Failed to restore from backup {selected}: {exc}")
            return None

    def list_backups(self, file_path: Path) -> list[Path]:
        """List all backup files for a given file, sorted newest-first.

        Backups are identified by the glob pattern ``{file_name}.bak.*``
        in the same directory as ``file_path``. Sorting uses the
        timestamp embedded in the filename first, falling back to file
        modification time as a secondary key.

        Args:
            file_path: Path to the original file.

        Returns:
            A list of backup :class:`Path` objects sorted newest-first.
            Returns an empty list if no backups exist or the parent
            directory does not exist.
        """
        if not file_path.parent.exists():
            return []

        pattern = f"{file_path.name}.bak.*"
        backups = list(file_path.parent.glob(pattern))

        # Sort by filename descending (timestamp is embedded in the name),
        # with mtime as a tiebreaker for edge cases
        backups.sort(key=lambda p: (p.name, p.stat().st_mtime), reverse=True)

        return backups
