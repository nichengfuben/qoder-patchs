"""Tests for qoder_patchs.core.patch_base module.

Covers PatchMetadata immutability, PatchStatus enum values,
PatchResult properties, PatchBase.validate, and PatchBase.info.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from qoder_patchs.core.patch_base import (
    PatchBase,
    PatchMetadata,
    PatchResult,
    PatchStatus,
)


class TestMetadataFrozen:
    """Test that PatchMetadata is immutable (frozen dataclass)."""

    def test_metadata_frozen(self):
        meta = PatchMetadata(
            name="test-patch",
            display_name="Test Patch",
            description="A test patch",
            version="1.0.0",
            author="tester",
            target_files=("file.js",),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            meta.name = "changed"  # type: ignore[misc]

    def test_metadata_fields(self):
        meta = PatchMetadata(
            name="my-patch",
            display_name="My Patch",
            description="Does something",
            version="2.0.0",
            author="me",
            target_files=("a.js", "b.mjs"),
            tags=("tag1", "tag2"),
            reversible=False,
        )
        assert meta.name == "my-patch"
        assert meta.display_name == "My Patch"
        assert meta.version == "2.0.0"
        assert meta.target_files == ("a.js", "b.mjs")
        assert meta.tags == ("tag1", "tag2")
        assert meta.reversible is False

    def test_metadata_defaults_tags(self):
        meta = PatchMetadata(
            name="x", display_name="X", description="d",
            version="1.0.0", author="a", target_files=("f.js",),
        )
        assert meta.tags == ()
        assert meta.reversible is True
        assert meta.min_cli_version is None
        assert meta.max_cli_version is None


class TestPatchStatusValues:
    """Test PatchStatus enum members."""

    def test_patch_status_values(self):
        assert PatchStatus.NOT_APPLIED.value == "not_applied"
        assert PatchStatus.APPLIED.value == "applied"
        assert PatchStatus.FAILED.value == "failed"
        assert PatchStatus.PARTIAL.value == "partial"
        assert PatchStatus.UNKNOWN.value == "unknown"

    def test_all_statuses_present(self):
        names = {s.name for s in PatchStatus}
        assert names == {"NOT_APPLIED", "APPLIED", "FAILED", "PARTIAL", "UNKNOWN"}


class TestPatchResult:
    """Test PatchResult dataclass and properties."""

    def test_result_success_property(self):
        result = PatchResult(
            status=PatchStatus.APPLIED,
            message="OK",
            patch_name="test",
        )
        assert result.success is True

    def test_result_not_success(self):
        result = PatchResult(
            status=PatchStatus.FAILED,
            message="Fail",
            patch_name="test",
            error="something went wrong",
        )
        assert result.success is False

    def test_result_not_applied_is_success(self):
        result = PatchResult(
            status=PatchStatus.NOT_APPLIED,
            message="Not applied",
            patch_name="test",
        )
        assert result.success is True

    def test_result_partial_not_success(self):
        result = PatchResult(
            status=PatchStatus.PARTIAL,
            message="Partial",
            patch_name="test",
        )
        assert result.success is False

    def test_result_unknown_not_success(self):
        result = PatchResult(
            status=PatchStatus.UNKNOWN,
            message="Unknown",
            patch_name="test",
        )
        assert result.success is False

    def test_result_defaults(self):
        result = PatchResult(
            status=PatchStatus.APPLIED,
            message="done",
            patch_name="test",
        )
        assert result.files_modified == []
        assert result.backups_created == []
        assert result.duration_ms == 0.0
        assert result.error is None
        assert result.timestamp is not None


class TestPatchBaseValidate:
    """Test PatchBase.validate method using a concrete subclass."""

    @pytest.fixture()
    def concrete_patch(self):
        """Create a minimal concrete PatchBase subclass for testing."""

        class ConcretePatch(PatchBase):
            @property
            def metadata(self) -> PatchMetadata:
                return PatchMetadata(
                    name="concrete",
                    display_name="Concrete Patch",
                    description="For testing",
                    version="1.0.0",
                    author="test",
                    target_files=("target.js", "other.mjs"),
                )

            def check(self, bundle_dir: Path) -> PatchStatus:
                return PatchStatus.UNKNOWN

            def apply(self, bundle_dir: Path, dry_run: bool = False) -> PatchResult:
                return PatchResult(
                    status=PatchStatus.APPLIED,
                    message="applied",
                    patch_name="concrete",
                )

            def rollback(self, bundle_dir: Path, backup_path=None) -> PatchResult:
                return PatchResult(
                    status=PatchStatus.NOT_APPLIED,
                    message="rolled back",
                    patch_name="concrete",
                )

        return ConcretePatch()

    def test_validate_missing_file(self, concrete_patch, tmp_path: Path):
        """validate() should report missing target files."""
        issues = concrete_patch.validate(tmp_path)
        assert len(issues) == 2
        assert "target.js" in issues[0]
        assert "other.mjs" in issues[1]

    def test_validate_existing_files(self, concrete_patch, tmp_path: Path):
        """validate() should return empty list when all files exist."""
        (tmp_path / "target.js").write_text("// target", encoding="utf-8")
        (tmp_path / "other.mjs").write_text("// other", encoding="utf-8")
        issues = concrete_patch.validate(tmp_path)
        assert issues == []

    def test_validate_partial_missing(self, concrete_patch, tmp_path: Path):
        """validate() should report only the missing file."""
        (tmp_path / "target.js").write_text("// target", encoding="utf-8")
        issues = concrete_patch.validate(tmp_path)
        assert len(issues) == 1
        assert "other.mjs" in issues[0]


class TestPatchBaseInfo:
    """Test PatchBase.info() formatted output."""

    def test_info_contains_key_fields(self):
        class InfoPatch(PatchBase):
            @property
            def metadata(self) -> PatchMetadata:
                return PatchMetadata(
                    name="info-test",
                    display_name="Info Test Patch",
                    description="Tests info output",
                    version="3.0.0",
                    author="tester",
                    target_files=("file.js",),
                    tags=("demo", "test"),
                    reversible=True,
                )

            def check(self, bundle_dir):
                return PatchStatus.UNKNOWN

            def apply(self, bundle_dir, dry_run=False):
                return PatchResult(status=PatchStatus.APPLIED, message="", patch_name="info-test")

            def rollback(self, bundle_dir, backup_path=None):
                return PatchResult(status=PatchStatus.NOT_APPLIED, message="", patch_name="info-test")

        patch = InfoPatch()
        info = patch.info()
        assert "Info Test Patch" in info
        assert "info-test" in info
        assert "3.0.0" in info
        assert "tester" in info
        assert "demo" in info
        assert "Yes" in info  # reversible
