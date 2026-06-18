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

import re
import time
from pathlib import Path
from typing import Optional

from loguru import logger

from qoder_patchs.core.patch_base import PatchBase, PatchMetadata, PatchResult, PatchStatus


# ---------------------------------------------------------------------------
# Compiled regex patterns (replace ``grep -oP`` invocations from the Bash version)
# ---------------------------------------------------------------------------

# Strategy 1: standard export mapping, e.g. ``isWindows10:()=>t2``
_EXPORT_PATTERN = re.compile(r"isWindows10:\(\)=>(\w+)")

# Strategy 2: fallback call-chain, e.g. ``t2()&&warnings.push({id:"windows-10"``
_FALLBACK_PATTERN = re.compile(r'(\w+)\(\)&&\w+\.push\(\{id:"windows-10"')

# Detection of an already-patched function, e.g. ``function t2(){return!1}``
_PATCHED_PATTERN = re.compile(r"function (\w+)\(\)\{return!1\}")


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
            if _PATCHED_PATTERN.search(content) and "isWindows10" in content:
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
        total_patched = 0
        total_skipped = 0
        total_failed = 0

        for fname in self.metadata.target_files:
            fpath = bundle_dir / fname
            if not fpath.exists():
                logger.warning("Target file does not exist, skipping: {}", fpath)
                continue

            content = fpath.read_text(encoding="utf-8", errors="ignore")

            # Step 1: detect the obfuscated isWindows10 function name
            func_name = self._detect_func_name(content, fname)
            if not func_name:
                logger.error("Cannot detect isWindows10 function name in {}", fname)
                total_failed += 1
                continue

            logger.debug("Detected function name '{}' in {}", func_name, fname)

            # Step 2: check whether already patched
            if re.search(
                rf"function {re.escape(func_name)}\(\)\{{return!1\}}", content
            ):
                logger.info("{} is already patched, skipping", fname)
                total_skipped += 1
                continue

            if dry_run:
                logger.info("[dry-run] Would patch {}", fpath)
                files_modified.append(fpath)
                continue

            # Step 3: backup original file
            backup = fpath.with_suffix(
                fpath.suffix + f".bak.{time.strftime('%Y%m%d%H%M%S')}"
            )
            backup.write_text(content, encoding="utf-8")
            backups_created.append(backup)
            logger.debug("Backup created: {}", backup)

            # Step 4: apply the patch (pure Python, replaces perl -i -pe)
            patched_content = self._do_patch(content, func_name)

            if patched_content and self._verify_patch(patched_content, func_name):
                fpath.write_text(patched_content, encoding="utf-8")
                files_modified.append(fpath)
                total_patched += 1
                logger.info("Successfully patched {}", fname)
            else:
                # Patch failed -- restore from backup
                fpath.write_text(content, encoding="utf-8")
                total_failed += 1
                logger.error("Patch failed for {}, restored from backup", fname)

        # -- Build result -------------------------------------------------
        status = PatchStatus.APPLIED if total_failed == 0 else PatchStatus.FAILED
        if total_skipped > 0 and total_patched == 0 and total_failed == 0:
            status = PatchStatus.APPLIED  # all files already patched
        if dry_run:
            status = PatchStatus.NOT_APPLIED

        msg_parts: list[str] = []
        if total_patched:
            msg_parts.append(f"已补丁 {total_patched} 个文件")
        if total_skipped:
            msg_parts.append(f"已跳过 {total_skipped} 个文件 (已补丁)")
        if total_failed:
            msg_parts.append(f"失败 {total_failed} 个文件")
        if dry_run:
            msg_parts.insert(0, "[预览模式]")
        message = "; ".join(msg_parts) if msg_parts else "无操作"

        return PatchResult(
            status=status,
            message=message,
            patch_name=self.metadata.name,
            files_modified=files_modified,
            backups_created=backups_created,
            duration_ms=(time.monotonic() - start) * 1000,
        )

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
        else:
            # Find the most recent backup for each target file
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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_func_name(self, content: str, fname: str) -> Optional[str]:
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
        # Strategy 1: standard export mapping
        match = _EXPORT_PATTERN.search(content)
        if match:
            logger.debug(
                "Detected function name via export mapping in {}: {}",
                fname,
                match.group(1),
            )
            return match.group(1)

        # Strategy 2: fallback call-chain
        match = _FALLBACK_PATTERN.search(content)
        if match:
            logger.debug(
                "Detected function name via fallback call-chain in {}: {}",
                fname,
                match.group(1),
            )
            return match.group(1)

        return None

    def _do_patch(self, content: str, func_name: str) -> Optional[str]:
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

        # Strategy 1: standard replacement (no nested braces)
        result = re.sub(
            rf"function {escaped}\(\)\{{[^}}]*\}}",
            f"function {func_name}(){{return!1}}",
            content,
        )
        if self._verify_patch(result, func_name):
            logger.debug("Patch applied via standard strategy for {}", func_name)
            return result

        # Strategy 2: extended replacement (handles nested braces)
        result = re.sub(
            rf"function {escaped}\(\)\{{.*?\}}function",
            f"function {func_name}(){{return!1}}function",
            content,
        )
        if self._verify_patch(result, func_name):
            logger.debug("Patch applied via extended strategy for {}", func_name)
            return result

        logger.error("Neither patching strategy succeeded for {}", func_name)
        return None

    def _verify_patch(self, content: str, func_name: str) -> bool:
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
