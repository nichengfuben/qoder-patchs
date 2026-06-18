"""Tests for qoder_patchs.utils.backup module.

Covers backup creation, cleanup of old backups, restoration,
and backup listing.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from qoder_patchs.utils.backup import BackupManager


@pytest.fixture()
def bm():
    """Return a BackupManager with default settings."""
    return BackupManager(keep_count=3)


@pytest.fixture()
def sample_file(tmp_path: Path) -> Path:
    """Create a sample file for backup tests."""
    f = tmp_path / "sample.js"
    f.write_text("// original content\nconsole.log('hello');\n", encoding="utf-8")
    return f


# ---------------------------------------------------------------------------
# create_backup
# ---------------------------------------------------------------------------


class TestCreateBackup:
    """Test BackupManager.create_backup."""

    def test_create_backup(self, bm: BackupManager, sample_file: Path):
        backup_path = bm.create_backup(sample_file)
        assert backup_path.exists()
        assert ".bak." in backup_path.name
        assert backup_path.parent == sample_file.parent

        # Backup should contain original content
        content = backup_path.read_text(encoding="utf-8")
        assert "original content" in content

    def test_create_backup_preserves_content(self, bm: BackupManager, sample_file: Path):
        backup_path = bm.create_backup(sample_file)
        assert backup_path.read_text(encoding="utf-8") == sample_file.read_text(encoding="utf-8")

    def test_create_backup_nonexistent_file(self, bm: BackupManager, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            bm.create_backup(tmp_path / "nonexistent.js")

    def test_create_multiple_backups(self, bm: BackupManager, sample_file: Path):
        b1 = bm.create_backup(sample_file)
        time.sleep(1.1)  # ensure different timestamp
        b2 = bm.create_backup(sample_file)
        assert b1 != b2
        assert b1.exists()
        assert b2.exists()


# ---------------------------------------------------------------------------
# cleanup_old_backups
# ---------------------------------------------------------------------------


class TestCleanupOldBackups:
    """Test BackupManager.cleanup_old_backups."""

    def test_cleanup_old_backups(self, bm: BackupManager, sample_file: Path):
        # Create more backups than keep_count (3)
        backups = []
        for i in range(5):
            b = bm.create_backup(sample_file)
            backups.append(b)
            time.sleep(1.1)

        # All 5 should exist before cleanup
        assert all(b.exists() for b in backups)

        # Cleanup keeping 3
        bm.cleanup_old_backups(sample_file, keep=3)

        remaining = bm.list_backups(sample_file)
        assert len(remaining) == 3

    def test_cleanup_within_limit(self, bm: BackupManager, sample_file: Path):
        """No cleanup needed when backup count is within limit."""
        bm.create_backup(sample_file)
        bm.create_backup(sample_file)

        bm.cleanup_old_backups(sample_file, keep=3)

        remaining = bm.list_backups(sample_file)
        assert len(remaining) == 2

    def test_cleanup_uses_default_keep(self, sample_file: Path):
        """cleanup_old_backups should use keep_count from constructor."""
        bm = BackupManager(keep_count=2)
        for _ in range(4):
            bm.create_backup(sample_file)
            time.sleep(1.1)

        bm.cleanup_old_backups(sample_file)  # uses default keep=2
        remaining = bm.list_backups(sample_file)
        assert len(remaining) == 2


# ---------------------------------------------------------------------------
# restore_from_backup
# ---------------------------------------------------------------------------


class TestRestoreFromBackup:
    """Test BackupManager.restore_from_backup."""

    def test_restore_from_backup(self, bm: BackupManager, sample_file: Path):
        # Create backup
        backup = bm.create_backup(sample_file)

        # Modify the original file
        sample_file.write_text("// modified content", encoding="utf-8")
        assert "modified" in sample_file.read_text(encoding="utf-8")

        # Restore from backup
        restored = bm.restore_from_backup(sample_file)
        assert restored is not None
        assert "original content" in sample_file.read_text(encoding="utf-8")

    def test_restore_from_specific_backup(self, bm: BackupManager, sample_file: Path):
        backup = bm.create_backup(sample_file)
        sample_file.write_text("// changed", encoding="utf-8")

        restored = bm.restore_from_backup(sample_file, backup_path=backup)
        assert restored == backup
        assert "original content" in sample_file.read_text(encoding="utf-8")

    def test_restore_no_backups(self, bm: BackupManager, tmp_path: Path):
        target = tmp_path / "no_backup.js"
        target.write_text("// current", encoding="utf-8")

        result = bm.restore_from_backup(target)
        assert result is None

    def test_restore_nonexistent_backup(self, bm: BackupManager, sample_file: Path):
        fake_backup = sample_file.parent / "fake.bak.20250101000000"
        result = bm.restore_from_backup(sample_file, backup_path=fake_backup)
        assert result is None


# ---------------------------------------------------------------------------
# list_backups
# ---------------------------------------------------------------------------


class TestListBackups:
    """Test BackupManager.list_backups."""

    def test_list_backups(self, bm: BackupManager, sample_file: Path):
        for _ in range(3):
            bm.create_backup(sample_file)
            time.sleep(1.1)

        backups = bm.list_backups(sample_file)
        assert len(backups) == 3

        # Should be sorted newest first
        names = [b.name for b in backups]
        assert names == sorted(names, reverse=True)

    def test_list_backups_empty(self, bm: BackupManager, tmp_path: Path):
        target = tmp_path / "no_backups.js"
        target.write_text("// no backups", encoding="utf-8")

        backups = bm.list_backups(target)
        assert backups == []

    def test_list_backups_nonexistent_parent(self, bm: BackupManager, tmp_path: Path):
        target = tmp_path / "nonexistent" / "file.js"
        backups = bm.list_backups(target)
        assert backups == []


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestBackupManagerInit:
    """Test BackupManager constructor."""

    def test_keep_count_default(self):
        bm = BackupManager()
        assert bm.keep_count == 3

    def test_keep_count_clamped_low(self):
        bm = BackupManager(keep_count=0)
        assert bm.keep_count == 1

    def test_keep_count_clamped_high(self):
        bm = BackupManager(keep_count=100)
        assert bm.keep_count == 10
