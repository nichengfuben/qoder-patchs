"""Windows 10 warning suppression patch.

Replaces the ``isWindows10()`` function in Qoder CLI bundle files so that it
always returns ``false``, eliminating the "Windows 10 detected" startup warning.

Ported from: ``patch-win10-warning.sh`` v2

Audit fixes applied:
  - No dependency on ``grep -P`` (PCRE); uses Python ``re`` module instead.
  - No dependency on ``perl``; uses pure Python string replacement.
  - Path handling uses ``pathlib`` + ``os.environ`` (replaces cygpath / MSYS paths).
  - Adds dependency pre-checks (npm, node).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from loguru import logger

from core.patch_base import PatchBase, PatchMetadata, PatchResult, PatchStatus
from patches.win10_detect import PATCHED_PATTERN, detect_func_name, do_patch, verify_patch


class Win10WarningPatch(PatchBase):
    """Patch that suppresses the Windows 10 detection warning in Qoder CLI.

    The patch works by replacing the body of the obfuscated ``isWindows10()``
    function with ``return!1`` (equivalent to ``return false``).  Two target
    files are patched:

    * ``qodercli.js`` -- main CLI entry point
    * ``qoder-worker-runtime.mjs`` -- worker runtime

    The function name is detected dynamically via two strategies (export
    mapping and fallback call-chain analysis).
    """

    # ------------------------------------------------------------------
    # PatchBase interface
    # ------------------------------------------------------------------

    @property
    def metadata(self) -> PatchMetadata:
        """Return patch metadata descriptor."""
        return PatchMetadata(
            name="win10-warning",
            display_name="Windows 10 警告抑制",
            description=(
                "将 isWindows10() 函数替换为始终返回 false, "
                "消除 Qoder CLI 启动时的 Windows 10 检测警告. "
                "同时补丁 qodercli.js (主入口) 和 qoder-worker-runtime.mjs (Worker)."
            ),
            version="2.0.0",
            author="nichengfuben",
            target_files=("qodercli.js", "qoder-worker-runtime.mjs"),
            min_cli_version=None,
            max_cli_version=None,
            tags=("warning", "windows10", "cosmetic"),
            reversible=True,
        )

    def check(self, bundle_dir: Path) -> PatchStatus:
        """Check current patch status across all target files (read-only).

        Args:
            bundle_dir: Path to the Qoder CLI bundle directory.

        Returns:
            The aggregate :class:`PatchStatus` across all existing target files.
        """
        results: list[bool] = []
        for fname in self.metadata.target_files:
            fpath = bundle_dir / fname
            if not fpath.exists():
                logger.debug("Target file missing, skipping: {}", fpath)
                continue
            content = fpath.read_text(encoding="utf-8", errors="ignore")
            if PATCHED_PATTERN.search(content) and "isWindows10" in content:
                results.append(True)
            else:
                results.append(False)

        if not results:
            return PatchStatus.UNKNOWN
        if all(results):
            return PatchStatus.APPLIED
        if any(results):
            return PatchStatus.PARTIAL
        return PatchStatus.NOT_APPLIED

    def apply(self, bundle_dir: Path, dry_run: bool = False) -> PatchResult:
        """Apply the Windows 10 warning suppression patch.

        Args:
            bundle_dir: Path to the Qoder CLI bundle directory.
            dry_run: If ``True``, simulate without modifying files.

        Returns:
            A :class:`PatchResult` describing the outcome.
        """
        start = time.monotonic()
        files_modified: list[Path] = []
        backups_created: list[Path] = []
        counters = {"patched": 0, "skipped": 0, "failed": 0}

        for fname in self.metadata.target_files:
            self._apply_single_file(
                bundle_dir, fname, dry_run, files_modified, backups_created, counters
            )

        status = self._build_apply_status(counters, dry_run)
        message = self._build_apply_message(counters, dry_run)

        return PatchResult(
            status=status,
            message=message,
            patch_name=self.metadata.name,
            files_modified=files_modified,
            backups_created=backups_created,
            duration_ms=(time.monotonic() - start) * 1000,
        )

    def _apply_single_file(
        self,
        bundle_dir: Path,
        fname: str,
        dry_run: bool,
        files_modified: list[Path],
        backups_created: list[Path],
        counters: dict[str, int],
    ) -> None:
        """Detect, back up, and patch a single target file.

        Args:
            bundle_dir: Path to the Qoder CLI bundle directory.
            fname: Target file name to patch.
            dry_run: If ``True``, simulate without modifying files.
            files_modified: Accumulator list of successfully modified paths.
            backups_created: Accumulator list of created backup paths.
            counters: Mutable dict tracking ``patched``/``skipped``/``failed`` counts.
        """
        fpath = bundle_dir / fname
        if not fpath.exists():
            logger.warning("Target file does not exist, skipping: {}", fpath)
            return

        content = fpath.read_text(encoding="utf-8", errors="ignore")

        func_name = detect_func_name(content, fname)
        if not func_name:
            logger.error("Cannot detect isWindows10 function name in {}", fname)
            counters["failed"] += 1
            return

        logger.debug("Detected function name '{}' in {}", func_name, fname)

        if self._is_already_patched(content, func_name, fname, counters):
            return

        if dry_run:
            logger.info("[dry-run] Would patch {}", fpath)
            files_modified.append(fpath)
            return

        self._backup_and_patch(
            fpath, fname, content, func_name, files_modified, backups_created, counters
        )

    def _is_already_patched(
        self, content: str, func_name: str, fname: str, counters: dict[str, int]
    ) -> bool:
        """Check whether *content* already has the patched function body.

        Args:
            content: Full text content of the target file.
            func_name: The detected obfuscated function name.
            fname: File name (for logging purposes).
            counters: Mutable dict tracking ``patched``/``skipped``/``failed`` counts.

        Returns:
            ``True`` if already patched (and ``counters["skipped"]`` was incremented).
        """
        if verify_patch(content, func_name):
            logger.info("{} is already patched, skipping", fname)
            counters["skipped"] += 1
            return True
        return False

    def _backup_and_patch(
        self,
        fpath: Path,
        fname: str,
        content: str,
        func_name: str,
        files_modified: list[Path],
        backups_created: list[Path],
        counters: dict[str, int],
    ) -> None:
        """Back up *fpath*, apply the patch, and verify the result.

        Args:
            fpath: Full path to the target file.
            fname: File name (for logging purposes).
            content: Original file content prior to patching.
            func_name: The obfuscated function name to patch.
            files_modified: Accumulator list of successfully modified paths.
            backups_created: Accumulator list of created backup paths.
            counters: Mutable dict tracking ``patched``/``skipped``/``failed`` counts.
        """
        backup = fpath.with_suffix(
            fpath.suffix + f".bak.{time.strftime('%Y%m%d%H%M%S')}"
        )
        backup.write_text(content, encoding="utf-8")
        backups_created.append(backup)
        logger.debug("Backup created: {}", backup)

        patched_content = do_patch(content, func_name)

        if patched_content and verify_patch(patched_content, func_name):
            fpath.write_text(patched_content, encoding="utf-8")
            files_modified.append(fpath)
            counters["patched"] += 1
            logger.info("Successfully patched {}", fname)
        else:
            fpath.write_text(content, encoding="utf-8")
            counters["failed"] += 1
            logger.error("Patch failed for {}, restored from backup", fname)

    def _build_apply_status(
        self, counters: dict[str, int], dry_run: bool
    ) -> PatchStatus:
        """Derive the aggregate :class:`PatchStatus` from per-file counters.

        Args:
            counters: Dict tracking ``patched``/``skipped``/``failed`` counts.
            dry_run: If ``True``, force a ``NOT_APPLIED`` status.

        Returns:
            The aggregate :class:`PatchStatus` for the apply operation.
        """
        status = PatchStatus.APPLIED if counters["failed"] == 0 else PatchStatus.FAILED
        if counters["skipped"] > 0 and counters["patched"] == 0 and counters["failed"] == 0:
            status = PatchStatus.APPLIED  # all files already patched
        if dry_run:
            status = PatchStatus.NOT_APPLIED
        return status

    def _build_apply_message(self, counters: dict[str, int], dry_run: bool) -> str:
        """Build the human-readable summary message for the apply result.

        Args:
            counters: Dict tracking ``patched``/``skipped``/``failed`` counts.
            dry_run: If ``True``, prefix the message with a preview marker.

        Returns:
            A semicolon-joined Chinese summary string, or ``"无操作"`` if empty.
        """
        msg_parts: list[str] = []
        if counters["patched"]:
            msg_parts.append(f"已补丁 {counters['patched']} 个文件")
        if counters["skipped"]:
            msg_parts.append(f"已跳过 {counters['skipped']} 个文件 (已补丁)")
        if counters["failed"]:
            msg_parts.append(f"失败 {counters['failed']} 个文件")
        if dry_run:
            msg_parts.insert(0, "[预览模式]")
        return "; ".join(msg_parts) if msg_parts else "无操作"

    def rollback(
        self, bundle_dir: Path, backup_path: Optional[Path] = None
    ) -> PatchResult:
        """Restore target files from backup.

        Args:
            bundle_dir: Path to the Qoder CLI bundle directory.
            backup_path: Optional specific backup file to restore from.
                If ``None``, the most recent backup is used for each file.

        Returns:
            A :class:`PatchResult` describing the rollback outcome.
        """
        start = time.monotonic()
        restored: list[Path] = []

        if backup_path and backup_path.exists():
            self._rollback_from_explicit_backup(bundle_dir, backup_path, restored)
        else:
            self._rollback_from_latest_backups(bundle_dir, restored)

        status = PatchStatus.NOT_APPLIED if restored else PatchStatus.FAILED
        return PatchResult(
            status=status,
            message=(
                f"已回滚 {len(restored)} 个文件" if restored else "未找到备份文件"
            ),
            patch_name=self.metadata.name,
            files_modified=restored,
            duration_ms=(time.monotonic() - start) * 1000,
        )

    def _rollback_from_explicit_backup(
        self, bundle_dir: Path, backup_path: Path, restored: list[Path]
    ) -> None:
        """Restore a single target file from an explicitly given backup path.

        Args:
            bundle_dir: Path to the Qoder CLI bundle directory.
            backup_path: The specific backup file to restore from.
            restored: Accumulator list of successfully restored target paths.
        """
        bak_marker = ".bak."
        idx = backup_path.name.find(bak_marker)
        if idx > 0:
            target_name = backup_path.name[:idx]
        else:
            target_name = backup_path.name.split(".")[0] + "." + backup_path.name.split(".")[1]
        target = bundle_dir / target_name
        if target.exists():
            target.write_text(
                backup_path.read_text(encoding="utf-8"), encoding="utf-8"
            )
            restored.append(target)
            logger.info("Restored {} from {}", target, backup_path)

    def _rollback_from_latest_backups(
        self, bundle_dir: Path, restored: list[Path]
    ) -> None:
        """Restore each target file from its most recent backup, if any.

        Args:
            bundle_dir: Path to the Qoder CLI bundle directory.
            restored: Accumulator list of successfully restored target paths.
        """
        for fname in self.metadata.target_files:
            backups = sorted(
                bundle_dir.glob(f"{fname}.bak.*"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if backups:
                target = bundle_dir / fname
                target.write_text(
                    backups[0].read_text(encoding="utf-8"), encoding="utf-8"
                )
                restored.append(target)
                logger.info("Restored {} from latest backup {}", target, backups[0])
