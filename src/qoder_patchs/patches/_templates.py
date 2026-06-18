"""Patch development template and reference.

This module provides a documented template class and helper patterns for
creating new patches.  It is **not** auto-discovered by the registry (the
leading underscore excludes it from ``pkgutil.iter_modules`` scans).

Usage::

    1. Copy :class:`_ExamplePatch` into a new module (e.g. ``my_patch.py``).
    2. Rename the class and fill in the ``metadata``, ``check``, ``apply``,
       and ``rollback`` implementations.
    3. Import the new class in ``patches/__init__.py`` so the registry can
       discover it.

Common patterns
---------------

Reading a file safely::

    content = fpath.read_text(encoding="utf-8", errors="ignore")

Creating a timestamped backup inline::

    backup = fpath.with_suffix(
        fpath.suffix + f".bak.{time.strftime('%Y%m%d%H%M%S')}"
    )
    backup.write_text(content, encoding="utf-8")

Using :class:`BackupManager` instead (recommended for production patches)::

    from qoder_patchs.utils.backup import BackupManager
    bm = BackupManager(keep_count=3)
    backup_path = bm.create_backup(fpath)
    bm.cleanup_old_backups(fpath)

Regex-based text replacement::

    import re
    result = re.sub(pattern, replacement, content)

Verifying a patch took effect::

    assert re.search(expected_pattern, patched_content)

"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Optional

from loguru import logger

from qoder_patchs.core.patch_base import PatchBase, PatchMetadata, PatchResult, PatchStatus


# ---------------------------------------------------------------------------
# Helper utilities (reusable across patches)
# ---------------------------------------------------------------------------


def read_file_text(path: Path) -> str:
    """Read a file as UTF-8 text, ignoring decode errors.

    Args:
        path: File path to read.

    Returns:
        The file contents as a string.

    Raises:
        FileNotFoundError: If *path* does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return path.read_text(encoding="utf-8", errors="ignore")


def create_inline_backup(path: Path) -> Path:
    """Create a timestamped backup copy alongside *path*.

    Naming convention: ``<original_name>.bak.<YYYYMMDDHHmmSS>``

    Args:
        path: The file to back up.

    Returns:
        Path to the created backup file.
    """
    timestamp = time.strftime("%Y%m%d%H%M%S")
    backup = path.with_suffix(path.suffix + f".bak.{timestamp}")
    backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    logger.debug("Inline backup created: {}", backup)
    return backup


def safe_regex_replace(
    content: str,
    pattern: str | re.Pattern[str],
    replacement: str,
    *,
    verify_pattern: str | re.Pattern[str] | None = None,
) -> Optional[str]:
    """Perform a regex substitution with optional verification.

    Args:
        content: Source text.
        pattern: Regex pattern to match.
        replacement: Replacement string (may use back-references).
        verify_pattern: If provided, the result is only returned when this
            pattern is found in the output.  Otherwise ``None`` is returned.

    Returns:
        The patched string, or ``None`` if verification failed.
    """
    result = re.sub(pattern, replacement, content)
    if verify_pattern is not None:
        if not re.search(verify_pattern, result):
            return None
    return result


# ---------------------------------------------------------------------------
# Template class (rename and customise for new patches)
# ---------------------------------------------------------------------------


class _ExamplePatch(PatchBase):
    """Template patch class -- copy and customise for new patches.

    This class is intentionally prefixed with an underscore so that the
    registry's auto-discovery mechanism skips it.
    """

    @property
    def metadata(self) -> PatchMetadata:
        """Return patch metadata.  Customise all fields for your patch."""
        return PatchMetadata(
            name="example-patch",
            display_name="Example Patch",
            description="A template demonstrating the patch structure.",
            version="1.0.0",
            author="your-name",
            target_files=("target-file.js",),
            min_cli_version=None,
            max_cli_version=None,
            tags=("example",),
            reversible=True,
        )

    def check(self, bundle_dir: Path) -> PatchStatus:
        """Check patch status (read-only).

        Typical implementation:
          1. Read each target file.
          2. Look for a marker that indicates the patch is applied.
          3. Aggregate results across all files.
        """
        for fname in self.metadata.target_files:
            fpath = bundle_dir / fname
            if not fpath.exists():
                continue
            content = read_file_text(fpath)
            # TODO: check for patch marker
            _ = content
        return PatchStatus.NOT_APPLIED

    def apply(self, bundle_dir: Path, dry_run: bool = False) -> PatchResult:
        """Apply the patch.

        Typical implementation:
          1. Validate prerequisites.
          2. For each target file:
             a. Detect the text to replace.
             b. Check if already patched (skip if so).
             c. Create a backup.
             d. Perform the replacement.
             e. Verify the replacement took effect.
          3. Return a :class:`PatchResult` with timing and file lists.
        """
        start = time.monotonic()
        files_modified: list[Path] = []
        backups_created: list[Path] = []

        for fname in self.metadata.target_files:
            fpath = bundle_dir / fname
            if not fpath.exists():
                continue

            content = read_file_text(fpath)

            if dry_run:
                files_modified.append(fpath)
                continue

            backup = create_inline_backup(fpath)
            backups_created.append(backup)

            # TODO: perform replacement
            patched = content  # placeholder

            fpath.write_text(patched, encoding="utf-8")
            files_modified.append(fpath)

        return PatchResult(
            status=PatchStatus.APPLIED,
            message="Template applied",
            patch_name=self.metadata.name,
            files_modified=files_modified,
            backups_created=backups_created,
            duration_ms=(time.monotonic() - start) * 1000,
        )

    def rollback(
        self, bundle_dir: Path, backup_path: Optional[Path] = None
    ) -> PatchResult:
        """Rollback from backup.

        Typical implementation:
          1. Locate the most recent backup (or use *backup_path*).
          2. Overwrite the target file with the backup contents.
        """
        start = time.monotonic()
        restored: list[Path] = []

        for fname in self.metadata.target_files:
            fpath = bundle_dir / fname
            backups = sorted(
                bundle_dir.glob(f"{fname}.bak.*"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if backups:
                fpath.write_text(
                    backups[0].read_text(encoding="utf-8"), encoding="utf-8"
                )
                restored.append(fpath)

        return PatchResult(
            status=PatchStatus.NOT_APPLIED if restored else PatchStatus.FAILED,
            message=f"Rolled back {len(restored)} file(s)" if restored else "No backups found",
            patch_name=self.metadata.name,
            files_modified=restored,
            duration_ms=(time.monotonic() - start) * 1000,
        )


# ---------------------------------------------------------------------------
# Checklist for creating a new patch
# ---------------------------------------------------------------------------

NEW_PATCH_CHECKLIST = """
New Patch Checklist
===================

1. [ ] Create ``src/qoder_patchs/patches/<snake_case>.py``
2. [ ] Class inherits from ``PatchBase``
3. [ ] ``metadata`` property returns a ``PatchMetadata`` with:
       - unique kebab-case ``name``
       - descriptive ``display_name``
       - semantic ``version``
       - correct ``target_files`` tuple
4. [ ] ``check()`` inspects target files and returns ``PatchStatus``
5. [ ] ``apply()`` creates backups before modifying files
6. [ ] ``apply()`` verifies the replacement took effect
7. [ ] ``rollback()`` restores from the most recent backup
8. [ ] Import the class in ``patches/__init__.py``
9. [ ] Add tests in ``test/patches/test_<name>.py``
10. [ ] Run ``python -c "from qoder_patchs.patches.<module> import <Class>"``
"""
