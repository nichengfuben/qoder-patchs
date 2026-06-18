"""Patch abstract base class and related data structures.

Defines the contract that all patches must implement, along with
standard metadata, status, and result structures.

Classes:
    PatchMetadata: Immutable patch descriptor (frozen dataclass).
    PatchStatus: Enum representing the current state of a patch.
    PatchResult: Mutable result of a patch operation.
    PatchBase: Abstract base class for all patches.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class PatchStatus(Enum):
    """Patch application status.

    Represents the current state of a patch relative to the target files.
    """

    NOT_APPLIED = "not_applied"
    """Patch has not been applied to any target file."""

    APPLIED = "applied"
    """Patch has been successfully applied to all target files."""

    FAILED = "failed"
    """Patch application failed."""

    PARTIAL = "partial"
    """Patch was applied to some but not all target files."""

    UNKNOWN = "unknown"
    """Status cannot be determined (e.g., target files missing)."""


@dataclass(frozen=True)
class PatchMetadata:
    """Immutable patch metadata.

    Stores descriptive information about a patch, including its identity,
    version, author, target files, and compatibility constraints.

    All collection fields use ``tuple`` instead of ``list`` to enforce
    immutability alongside ``frozen=True``.

    Attributes:
        name: Unique identifier in kebab-case (e.g., ``"win10-warning"``).
        display_name: Human-readable name (e.g., ``"Windows 10 Warning Suppression"``).
        description: Detailed description of what the patch does.
        version: Semantic version string (e.g., ``"2.0.0"``).
        author: Patch author name.
        target_files: Tuple of target file names the patch operates on.
        min_cli_version: Minimum compatible Qoder CLI version, or ``None``.
        max_cli_version: Maximum compatible Qoder CLI version, or ``None``.
        tags: Tuple of categorization tags (e.g., ``("warning", "windows10")``).
        reversible: Whether the patch supports rollback.
    """

    name: str
    display_name: str
    description: str
    version: str
    author: str
    target_files: tuple[str, ...]
    min_cli_version: Optional[str] = None
    max_cli_version: Optional[str] = None
    tags: tuple[str, ...] = ()
    reversible: bool = True


@dataclass
class PatchResult:
    """Result of a patch operation (apply or rollback).

    Captures the outcome of a patch operation including status, timing,
    affected files, and any error information.

    Attributes:
        status: The resulting patch status.
        message: Human-readable result summary.
        patch_name: Name of the patch that was executed.
        files_modified: List of file paths that were modified.
        backups_created: List of backup file paths created during the operation.
        duration_ms: Operation duration in milliseconds.
        error: Error message if the operation failed, or ``None``.
        timestamp: When the operation completed.
    """

    status: PatchStatus
    message: str
    patch_name: str
    files_modified: list[Path] = field(default_factory=list)
    backups_created: list[Path] = field(default_factory=list)
    duration_ms: float = 0.0
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def success(self) -> bool:
        """Whether the patch operation was successful."""
        return self.status == PatchStatus.APPLIED


class PatchBase(ABC):
    """Abstract base class for all patches.

    Every patch must subclass ``PatchBase`` and implement the four abstract
    members: :attr:`metadata`, :meth:`check`, :meth:`apply`, and
    :meth:`rollback`.

    Concrete methods :meth:`validate` and :meth:`info` provide common
    functionality shared across all patches.

    Example usage::

        class MyPatch(PatchBase):
            @property
            def metadata(self) -> PatchMetadata:
                return PatchMetadata(
                    name="my-patch",
                    display_name="My Patch",
                    description="Does something useful",
                    version="1.0.0",
                    author="me",
                    target_files=("target.js",),
                )

            def check(self, bundle_dir: Path) -> PatchStatus:
                ...

            def apply(self, bundle_dir: Path, dry_run: bool = False) -> PatchResult:
                ...

            def rollback(self, bundle_dir: Path, backup_path: Optional[Path] = None) -> PatchResult:
                ...
    """

    @property
    @abstractmethod
    def metadata(self) -> PatchMetadata:
        """Return the patch metadata descriptor.

        This must be a property that returns a :class:`PatchMetadata`
        instance describing the patch.
        """
        ...

    @abstractmethod
    def check(self, bundle_dir: Path) -> PatchStatus:
        """Check the current status of this patch (read-only).

        Inspects target files in ``bundle_dir`` to determine whether the
        patch has been applied, without modifying any files.

        Args:
            bundle_dir: Path to the Qoder CLI bundle directory.

        Returns:
            The current :class:`PatchStatus` of this patch.
        """
        ...

    @abstractmethod
    def apply(self, bundle_dir: Path, dry_run: bool = False) -> PatchResult:
        """Apply the patch to target files.

        When ``dry_run`` is ``True``, the method should simulate the patch
        without modifying any files, returning a result indicating what
        would be changed.

        Args:
            bundle_dir: Path to the Qoder CLI bundle directory.
            dry_run: If ``True``, simulate without modifying files.

        Returns:
            A :class:`PatchResult` describing the outcome.
        """
        ...

    @abstractmethod
    def rollback(
        self, bundle_dir: Path, backup_path: Optional[Path] = None
    ) -> PatchResult:
        """Rollback (undo) a previously applied patch.

        If ``backup_path`` is provided, restores from that specific backup.
        Otherwise, searches for the most recent backup automatically.

        Args:
            bundle_dir: Path to the Qoder CLI bundle directory.
            backup_path: Optional specific backup file to restore from.

        Returns:
            A :class:`PatchResult` describing the rollback outcome.
        """
        ...

    def validate(self, bundle_dir: Path) -> list[str]:
        """Validate whether the patch can be safely applied.

        Checks that all target files exist and are writable. Returns a list
        of issue descriptions. An empty list means the patch can proceed.

        Args:
            bundle_dir: Path to the Qoder CLI bundle directory.

        Returns:
            A list of human-readable issue strings. Empty if no issues found.
        """
        issues: list[str] = []
        for fname in self.metadata.target_files:
            fpath = bundle_dir / fname
            if not fpath.exists():
                issues.append(f"Target file does not exist: {fname}")
            elif not os.access(fpath, os.W_OK):
                issues.append(f"Target file is not writable: {fname}")
        return issues

    def info(self) -> str:
        """Return a formatted human-readable info summary of this patch.

        Useful for CLI display when listing available patches or showing
        patch details.

        Returns:
            A multi-line string with patch information.
        """
        m = self.metadata
        lines = [
            f"Name: {m.display_name} ({m.name})",
            f"Version: {m.version}",
            f"Author: {m.author}",
            f"Description: {m.description}",
            f"Target files: {', '.join(m.target_files)}",
            f"Reversible: {'Yes' if m.reversible else 'No'}",
        ]
        if m.tags:
            lines.append(f"Tags: {', '.join(m.tags)}")
        if m.min_cli_version:
            lines.append(f"Min CLI version: {m.min_cli_version}")
        if m.max_cli_version:
            lines.append(f"Max CLI version: {m.max_cli_version}")
        return "\n".join(lines)
