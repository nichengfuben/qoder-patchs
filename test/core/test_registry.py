"""Tests for qoder_patchs.core.registry module.

Covers manual registration, lookup, builtin discovery,
and name enumeration.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from qoder_patchs.core.patch_base import (
    PatchBase,
    PatchMetadata,
    PatchResult,
    PatchStatus,
)
from qoder_patchs.core.registry import PatchRegistry


# ---------------------------------------------------------------------------
# Test helper: minimal concrete patch
# ---------------------------------------------------------------------------


def _make_patch(name: str) -> PatchBase:
    """Create a minimal concrete patch instance with the given name."""

    class _Stub(PatchBase):
        @property
        def metadata(self) -> PatchMetadata:
            return PatchMetadata(
                name=name,
                display_name=name.replace("-", " ").title(),
                description=f"Stub patch: {name}",
                version="1.0.0",
                author="test",
                target_files=("stub.js",),
            )

        def check(self, bundle_dir: Path) -> PatchStatus:
            return PatchStatus.UNKNOWN

        def apply(self, bundle_dir: Path, dry_run: bool = False) -> PatchResult:
            return PatchResult(
                status=PatchStatus.APPLIED, message="ok", patch_name=name
            )

        def rollback(self, bundle_dir: Path, backup_path=None) -> PatchResult:
            return PatchResult(
                status=PatchStatus.NOT_APPLIED, message="ok", patch_name=name
            )

    return _Stub()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRegisterAndGet:
    """Test manual registration and lookup."""

    def test_register_and_get(self):
        registry = PatchRegistry()
        patch = _make_patch("alpha")
        registry.register(patch)

        result = registry.get("alpha")
        assert result is not None
        assert result.metadata.name == "alpha"

    def test_register_multiple(self):
        registry = PatchRegistry()
        registry.register(_make_patch("a"))
        registry.register(_make_patch("b"))
        registry.register(_make_patch("c"))

        assert len(registry.get_all()) == 3

    def test_register_replaces_existing(self):
        registry = PatchRegistry()
        p1 = _make_patch("dup")
        p2 = _make_patch("dup")
        registry.register(p1)
        registry.register(p2)

        # Should have only one entry
        assert len(registry.get_all()) == 1
        # The second registration replaces the first
        assert registry.get("dup") is p2


class TestDiscoverBuiltin:
    """Test automatic discovery of built-in patches."""

    def test_discover_builtin(self):
        registry = PatchRegistry()
        registry.discover_builtin()

        # The project has at least win10-warning as a built-in patch
        names = registry.names()
        assert "win10-warning" in names

    def test_discover_builtin_returns_instances(self):
        registry = PatchRegistry()
        registry.discover_builtin()

        patch = registry.get("win10-warning")
        assert patch is not None
        assert isinstance(patch, PatchBase)
        assert patch.metadata.name == "win10-warning"


class TestGetNonexistent:
    """Test looking up patches that don't exist."""

    def test_get_nonexistent(self):
        registry = PatchRegistry()
        result = registry.get("does-not-exist")
        assert result is None

    def test_get_from_empty(self):
        registry = PatchRegistry()
        assert registry.get_all() == {}


class TestNames:
    """Test the names() method."""

    def test_names(self):
        registry = PatchRegistry()
        registry.register(_make_patch("charlie"))
        registry.register(_make_patch("alpha"))
        registry.register(_make_patch("bravo"))

        names = registry.names()
        assert names == ["alpha", "bravo", "charlie"]  # sorted

    def test_names_empty(self):
        registry = PatchRegistry()
        assert registry.names() == []


class TestDiscoverEntryPoints:
    """Test entry-point discovery (should not crash even without external patches)."""

    def test_discover_entry_points_no_crash(self):
        registry = PatchRegistry()
        # Should not raise even if no external patches exist
        registry.discover_entry_points()
