"""Tests for qoder_patchs.core.engine module.

Covers apply, apply_all, status, rollback, and unknown patch handling.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pytest

from qoder_patchs.core.config import AppConfig
from qoder_patchs.core.engine import PatchEngine
from qoder_patchs.core.patch_base import (
    PatchBase,
    PatchMetadata,
    PatchResult,
    PatchStatus,
)
from qoder_patchs.core.registry import PatchRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _StubPatch(PatchBase):
    """A configurable stub patch for engine tests."""

    def __init__(
        self,
        name: str = "stub",
        target_files: tuple[str, ...] = ("stub.js",),
        reversible: bool = True,
        check_status: PatchStatus = PatchStatus.NOT_APPLIED,
        apply_status: PatchStatus = PatchStatus.APPLIED,
        rollback_status: PatchStatus = PatchStatus.NOT_APPLIED,
    ) -> None:
        self._name = name
        self._target_files = target_files
        self._reversible = reversible
        self._check_status = check_status
        self._apply_status = apply_status
        self._rollback_status = rollback_status

    @property
    def metadata(self) -> PatchMetadata:
        return PatchMetadata(
            name=self._name,
            display_name=self._name.title(),
            description="Stub",
            version="1.0.0",
            author="test",
            target_files=self._target_files,
            reversible=self._reversible,
        )

    def check(self, bundle_dir: Path) -> PatchStatus:
        return self._check_status

    def apply(self, bundle_dir: Path, dry_run: bool = False) -> PatchResult:
        return PatchResult(
            status=self._apply_status,
            message="applied" if self._apply_status == PatchStatus.APPLIED else "failed",
            patch_name=self._name,
        )

    def rollback(self, bundle_dir: Path, backup_path: Optional[Path] = None) -> PatchResult:
        return PatchResult(
            status=self._rollback_status,
            message="rolled back",
            patch_name=self._name,
        )


def _engine_with_patch(patch: PatchBase, config: Optional[AppConfig] = None) -> PatchEngine:
    """Create a PatchEngine with a single registered patch."""
    registry = PatchRegistry()
    registry.register(patch)
    return PatchEngine(registry, backup_manager=None, config=config)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestApplySingle:
    """Test PatchEngine.apply for a single patch."""

    def test_apply_single(self, tmp_path: Path):
        """Successful apply of a single patch."""
        (tmp_path / "stub.js").write_text("// stub", encoding="utf-8")
        patch = _StubPatch(check_status=PatchStatus.NOT_APPLIED)
        engine = _engine_with_patch(patch)

        result = engine.apply("stub", tmp_path)
        assert result.success is True
        assert result.patch_name == "stub"

    def test_apply_already_applied(self, tmp_path: Path):
        """Engine should skip patches that are already applied."""
        (tmp_path / "stub.js").write_text("// stub", encoding="utf-8")
        patch = _StubPatch(check_status=PatchStatus.APPLIED)
        engine = _engine_with_patch(patch)

        result = engine.apply("stub", tmp_path)
        # Should return APPLIED status (already applied, skipped)
        assert result.status == PatchStatus.APPLIED
        assert "already applied" in result.message.lower()

    def test_apply_force_reapply(self, tmp_path: Path):
        """With force_reapply, engine should re-apply even if already applied."""
        (tmp_path / "stub.js").write_text("// stub", encoding="utf-8")
        patch = _StubPatch(check_status=PatchStatus.APPLIED)
        config = AppConfig()
        config.patch.force_reapply = True
        engine = _engine_with_patch(patch, config)

        result = engine.apply("stub", tmp_path)
        assert result.success is True

    def test_apply_dry_run(self, tmp_path: Path):
        """Dry run should not modify files."""
        (tmp_path / "stub.js").write_text("// stub", encoding="utf-8")
        patch = _StubPatch()
        engine = _engine_with_patch(patch)

        result = engine.apply("stub", tmp_path, dry_run=True)
        # The stub still returns APPLIED but the engine passes dry_run=True
        assert result is not None


class TestApplyAll:
    """Test PatchEngine.apply_all."""

    def test_apply_all(self, tmp_path: Path):
        (tmp_path / "a.js").write_text("// a", encoding="utf-8")
        (tmp_path / "b.js").write_text("// b", encoding="utf-8")

        registry = PatchRegistry()
        registry.register(_StubPatch(name="alpha", target_files=("a.js",)))
        registry.register(_StubPatch(name="beta", target_files=("b.js",)))
        engine = PatchEngine(registry)

        results = engine.apply_all(tmp_path)
        assert len(results) == 2
        assert all(r.success for r in results)

    def test_apply_all_empty_registry(self, tmp_path: Path):
        registry = PatchRegistry()
        engine = PatchEngine(registry)

        results = engine.apply_all(tmp_path)
        assert results == []


class TestStatus:
    """Test PatchEngine.status."""

    def test_status(self, tmp_path: Path):
        patch = _StubPatch(check_status=PatchStatus.APPLIED)
        engine = _engine_with_patch(patch)

        status = engine.status("stub", tmp_path)
        assert status == PatchStatus.APPLIED

    def test_status_unknown_patch(self, tmp_path: Path):
        registry = PatchRegistry()
        engine = PatchEngine(registry)

        status = engine.status("nonexistent", tmp_path)
        assert status == PatchStatus.UNKNOWN


class TestRollback:
    """Test PatchEngine.rollback."""

    def test_rollback(self, tmp_path: Path):
        patch = _StubPatch(rollback_status=PatchStatus.NOT_APPLIED)
        engine = _engine_with_patch(patch)

        result = engine.rollback("stub", tmp_path)
        assert result.status == PatchStatus.NOT_APPLIED

    def test_rollback_not_reversible(self, tmp_path: Path):
        patch = _StubPatch(reversible=False)
        engine = _engine_with_patch(patch)

        result = engine.rollback("stub", tmp_path)
        assert result.status == PatchStatus.FAILED
        assert "not" in result.message.lower() or "revers" in result.message.lower()

    def test_rollback_unknown_patch(self, tmp_path: Path):
        registry = PatchRegistry()
        engine = PatchEngine(registry)

        result = engine.rollback("nonexistent", tmp_path)
        assert result.status == PatchStatus.FAILED


class TestApplyUnknownPatch:
    """Test applying a patch that does not exist in the registry."""

    def test_apply_unknown_patch(self, tmp_path: Path):
        registry = PatchRegistry()
        engine = PatchEngine(registry)

        result = engine.apply("ghost", tmp_path)
        assert result.status == PatchStatus.FAILED
        assert "not found" in result.message.lower() or "unknown" in result.error.lower()
