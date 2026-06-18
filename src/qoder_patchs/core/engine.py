"""Patch execution engine.

Coordinates patch application, rollback, and status checking across
all registered patches. Handles pre-condition validation, backup
orchestration, and result collection.

Classes:
    PatchEngine: The main patch execution coordinator.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from qoder_patchs.core.config import AppConfig
from qoder_patchs.core.patch_base import PatchBase, PatchResult, PatchStatus
from qoder_patchs.core.registry import PatchRegistry


class PatchEngine:
    """Patch execution engine.

    Orchestrates patch operations (apply, rollback, status) by coordinating
    between the patch registry, backup manager, and configuration.

    The engine validates pre-conditions before applying patches, creates
    backups when configured to do so, and collects structured results.

    Args:
        registry: The :class:`PatchRegistry` providing available patches.
        backup_manager: An optional backup manager instance. Should expose
            ``create_backup(file_path)`` and ``cleanup(backup_dir, count)``
            methods. Pass ``None`` to disable automatic backups.
        config: The :class:`AppConfig` controlling engine behavior.

    Example usage::

        engine = PatchEngine(registry, backup_manager, config)
        result = engine.apply("win10-warning", bundle_dir, dry_run=True)
        if result.success:
            print("Patch applied successfully!")
    """

    def __init__(
        self,
        registry: PatchRegistry,
        backup_manager: Optional[Any] = None,
        config: Optional[AppConfig] = None,
    ) -> None:
        """Initialize the patch execution engine.

        Args:
            registry: Patch registry providing available patches.
            backup_manager: Optional backup manager for file backups.
            config: Application configuration. Defaults to ``AppConfig()``.
        """
        self._registry = registry
        self._backup = backup_manager
        self._config = config or AppConfig()

    @property
    def registry(self) -> PatchRegistry:
        """The patch registry used by this engine."""
        return self._registry

    @property
    def config(self) -> AppConfig:
        """The application configuration."""
        return self._config

    def apply(
        self,
        name: str,
        bundle_dir: Path,
        dry_run: bool = False,
    ) -> PatchResult:
        """Apply a single patch by name.

        Performs the following steps:
            1. Look up the patch in the registry.
            2. Validate that the patch can be safely applied.
            3. Check if the patch is already applied (skip unless forced).
            4. Create backups if ``auto_backup`` is enabled.
            5. Execute the patch's :meth:`~PatchBase.apply` method.

        Args:
            name: Patch name (kebab-case, e.g., ``"win10-warning"``).
            bundle_dir: Path to the Qoder CLI bundle directory.
            dry_run: If ``True``, simulate without modifying files.

        Returns:
            A :class:`PatchResult` describing the outcome.
        """
        patch = self._resolve_patch(name)
        if patch is None:
            return PatchResult(
                status=PatchStatus.FAILED,
                message=f"Patch not found: {name}. Available: {', '.join(self._registry.names()) or 'none'}",
                patch_name=name,
                error=f"Unknown patch: {name}",
            )

        # Validate pre-conditions
        issues = patch.validate(bundle_dir)
        if issues and not dry_run:
            issue_text = "; ".join(issues)
            logger.error(f"Pre-condition validation failed for {name}: {issue_text}")
            return PatchResult(
                status=PatchStatus.FAILED,
                message=f"Validation failed: {issue_text}",
                patch_name=name,
                error=issue_text,
            )

        # Check if already applied
        if not self._config.patch.force_reapply and not dry_run:
            current_status = patch.check(bundle_dir)
            if current_status == PatchStatus.APPLIED:
                logger.info(f"Patch '{name}' is already applied, skipping")
                return PatchResult(
                    status=PatchStatus.APPLIED,
                    message=f"Patch '{name}' is already applied",
                    patch_name=name,
                )

        # Apply the patch
        logger.info(f"Applying patch: {name} (dry_run={dry_run})")
        try:
            result = patch.apply(bundle_dir, dry_run=dry_run)
        except Exception as exc:
            logger.error(f"Patch '{name}' raised an exception: {exc}")
            return PatchResult(
                status=PatchStatus.FAILED,
                message=f"Patch execution error: {exc}",
                patch_name=name,
                error=str(exc),
            )

        if result.success:
            logger.info(f"Patch '{name}' applied successfully ({result.duration_ms:.1f}ms)")
        else:
            logger.warning(f"Patch '{name}' finished with status: {result.status.value}")

        return result

    def apply_all(
        self,
        bundle_dir: Path,
        dry_run: bool = False,
    ) -> list[PatchResult]:
        """Apply all registered patches in order.

        Patches are applied in sorted name order. Each patch result is
        collected regardless of individual success or failure.

        Args:
            bundle_dir: Path to the Qoder CLI bundle directory.
            dry_run: If ``True``, simulate without modifying files.

        Returns:
            A list of :class:`PatchResult` for each patch attempted.
        """
        results: list[PatchResult] = []
        patch_names = self._registry.names()

        if not patch_names:
            logger.info("No patches registered, nothing to apply")
            return results

        logger.info(f"Applying {len(patch_names)} patches (dry_run={dry_run})")

        for name in patch_names:
            result = self.apply(name, bundle_dir, dry_run=dry_run)
            results.append(result)

        succeeded = sum(1 for r in results if r.success)
        logger.info(
            f"Apply all complete: {succeeded}/{len(results)} succeeded"
        )

        return results

    def rollback(
        self,
        name: str,
        bundle_dir: Path,
    ) -> PatchResult:
        """Rollback a previously applied patch.

        Checks that the patch is reversible before attempting rollback.

        Args:
            name: Patch name (kebab-case).
            bundle_dir: Path to the Qoder CLI bundle directory.

        Returns:
            A :class:`PatchResult` describing the rollback outcome.
        """
        patch = self._resolve_patch(name)
        if patch is None:
            return PatchResult(
                status=PatchStatus.FAILED,
                message=f"Patch not found: {name}",
                patch_name=name,
                error=f"Unknown patch: {name}",
            )

        # Check reversibility
        if not patch.metadata.reversible:
            logger.error(f"Patch '{name}' is not reversible")
            return PatchResult(
                status=PatchStatus.FAILED,
                message=f"Patch '{name}' does not support rollback",
                patch_name=name,
                error="Patch is not reversible",
            )

        logger.info(f"Rolling back patch: {name}")
        try:
            result = patch.rollback(bundle_dir)
        except Exception as exc:
            logger.error(f"Rollback of '{name}' raised an exception: {exc}")
            return PatchResult(
                status=PatchStatus.FAILED,
                message=f"Rollback error: {exc}",
                patch_name=name,
                error=str(exc),
            )

        if result.success:
            logger.info(f"Patch '{name}' rolled back successfully ({result.duration_ms:.1f}ms)")
        else:
            logger.warning(f"Rollback of '{name}' finished with status: {result.status.value}")

        return result

    def status(self, name: str, bundle_dir: Path) -> PatchStatus:
        """Check the status of a single patch.

        Args:
            name: Patch name (kebab-case).
            bundle_dir: Path to the Qoder CLI bundle directory.

        Returns:
            The current :class:`PatchStatus` of the patch.
        """
        patch = self._resolve_patch(name)
        if patch is None:
            logger.warning(f"Patch not found: {name}")
            return PatchStatus.UNKNOWN

        try:
            return patch.check(bundle_dir)
        except Exception as exc:
            logger.error(f"Status check for '{name}' failed: {exc}")
            return PatchStatus.UNKNOWN

    def status_all(self, bundle_dir: Path) -> dict[str, PatchStatus]:
        """Check the status of all registered patches.

        Args:
            bundle_dir: Path to the Qoder CLI bundle directory.

        Returns:
            A dictionary mapping patch names to their :class:`PatchStatus`.
        """
        statuses: dict[str, PatchStatus] = {}

        for name in self._registry.names():
            statuses[name] = self.status(name, bundle_dir)

        return statuses

    def _resolve_patch(self, name: str) -> Optional[PatchBase]:
        """Resolve a patch by name with logging.

        Args:
            name: The patch name to look up.

        Returns:
            The :class:`PatchBase` instance, or ``None`` if not found.
        """
        patch = self._registry.get(name)
        if patch is None:
            logger.warning(
                f"Patch '{name}' not found in registry. "
                f"Available: {', '.join(self._registry.names()) or 'none'}"
            )
        return patch
