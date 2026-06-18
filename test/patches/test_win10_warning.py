"""Tests for qoder_patchs.patches.win10_warning module.

This is the MOST IMPORTANT test file. It covers the complete lifecycle
of the Windows 10 warning suppression patch:
- Function name detection (standard and fallback)
- Status checking (applied / not applied)
- Apply (normal, dry run, already patched)
- Backup creation
- Rollback from backup
- Full cycle: apply -> verify -> rollback -> verify
"""

from __future__ import annotations

import re
import time
from pathlib import Path

import pytest

from qoder_patchs.core.patch_base import PatchResult, PatchStatus
from qoder_patchs.patches.win10_warning import (
    Win10WarningPatch,
    _EXPORT_PATTERN,
    _FALLBACK_PATTERN,
    _PATCHED_PATTERN,
)


@pytest.fixture()
def patch_instance():
    """Return a fresh Win10WarningPatch instance."""
    return Win10WarningPatch()


# ---------------------------------------------------------------------------
# Function name detection
# ---------------------------------------------------------------------------


class TestDetectFuncNameStandard:
    """Test _detect_func_name via the standard export mapping strategy."""

    def test_detect_func_name_standard(self, patch_instance):
        content = 'var m={isWindows10:()=>t2,isLinux:()=>t1};'
        name = patch_instance._detect_func_name(content, "test.js")
        assert name == "t2"

    def test_detect_func_name_longer_name(self, patch_instance):
        content = 'exports={isWindows10:()=>_isWin10Check};'
        name = patch_instance._detect_func_name(content, "test.js")
        assert name == "_isWin10Check"

    def test_detect_standard_pattern_regex(self):
        """Verify the compiled regex matches expected patterns."""
        text = 'isWindows10:()=>abc123'
        m = _EXPORT_PATTERN.search(text)
        assert m is not None
        assert m.group(1) == "abc123"


class TestDetectFuncNameFallback:
    """Test _detect_func_name via the fallback call-chain strategy."""

    def test_detect_func_name_fallback(self, patch_instance):
        content = 'function myFunc(){return!0}if(myFunc()&&warnings.push({id:"windows-10"'
        name = patch_instance._detect_func_name(content, "test.js")
        assert name == "myFunc"

    def test_detect_fallback_pattern_regex(self):
        """Verify the fallback regex matches expected patterns."""
        text = 't99()&&errs.push({id:"windows-10"'
        m = _FALLBACK_PATTERN.search(text)
        assert m is not None
        assert m.group(1) == "t99"

    def test_detect_func_name_not_found(self, patch_instance):
        content = 'var x = 42; console.log("hello");'
        name = patch_instance._detect_func_name(content, "test.js")
        assert name is None


# ---------------------------------------------------------------------------
# Status checking
# ---------------------------------------------------------------------------


class TestCheckNotApplied:
    """Test check() when the patch has NOT been applied."""

    def test_check_not_applied(self, patch_instance, temp_bundle: Path):
        status = patch_instance.check(temp_bundle)
        assert status == PatchStatus.NOT_APPLIED

    def test_check_missing_bundle(self, patch_instance, tmp_path: Path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        status = patch_instance.check(empty_dir)
        assert status == PatchStatus.UNKNOWN


class TestCheckApplied:
    """Test check() when the patch HAS been applied."""

    def test_check_applied(self, patch_instance, patched_bundle: Path):
        status = patch_instance.check(patched_bundle)
        assert status == PatchStatus.APPLIED

    def test_check_partial(self, patch_instance, tmp_path: Path):
        """One file patched, one not -> PARTIAL."""
        bundle = tmp_path / "partial"
        bundle.mkdir()

        # qodercli.js: patched
        patched_content = (
            'var m={isWindows10:()=>t2};\n'
            'function t2(){return!1}\n'
        )
        (bundle / "qodercli.js").write_text(patched_content, encoding="utf-8")

        # qoder-worker-runtime.mjs: NOT patched
        unpatched_content = (
            'var w={isWindows10:()=>w2};\n'
            'function w2(){var e=navigator.userAgent;return e.indexOf("Windows NT 10.0")>-1}\n'
        )
        (bundle / "qoder-worker-runtime.mjs").write_text(unpatched_content, encoding="utf-8")

        status = patch_instance.check(bundle)
        assert status == PatchStatus.PARTIAL


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


class TestApplySuccess:
    """Test successful patch application."""

    def test_apply_success(self, patch_instance, temp_bundle: Path):
        result = patch_instance.apply(temp_bundle)
        assert result.success is True
        assert result.status == PatchStatus.APPLIED
        assert len(result.files_modified) == 2
        assert result.duration_ms >= 0

        # Verify files are actually patched
        for fname in ("qodercli.js", "qoder-worker-runtime.mjs"):
            content = (temp_bundle / fname).read_text(encoding="utf-8")
            assert "return!1" in content


class TestApplyDryRun:
    """Test dry-run mode (no file modifications)."""

    def test_apply_dry_run(self, patch_instance, temp_bundle: Path):
        # Read original content
        original_cli = (temp_bundle / "qodercli.js").read_text(encoding="utf-8")
        original_worker = (temp_bundle / "qoder-worker-runtime.mjs").read_text(encoding="utf-8")

        result = patch_instance.apply(temp_bundle, dry_run=True)

        # Dry run should NOT change files
        assert (temp_bundle / "qodercli.js").read_text(encoding="utf-8") == original_cli
        assert (temp_bundle / "qoder-worker-runtime.mjs").read_text(encoding="utf-8") == original_worker

        # Status should be NOT_APPLIED (since we didn't actually patch)
        assert result.status == PatchStatus.NOT_APPLIED
        assert "[预览模式]" in result.message


class TestApplyAlreadyPatched:
    """Test applying to already-patched files."""

    def test_apply_already_patched(self, patch_instance, patched_bundle: Path):
        result = patch_instance.apply(patched_bundle)
        # Should succeed (all files skipped because already patched)
        assert result.status == PatchStatus.APPLIED
        assert "跳过" in result.message or "skipped" in result.message.lower()
        assert len(result.files_modified) == 0


class TestApplyBackupCreated:
    """Test that backups are created during apply."""

    def test_apply_backup_created(self, patch_instance, temp_bundle: Path):
        result = patch_instance.apply(temp_bundle)
        assert result.success is True
        assert len(result.backups_created) == 2

        for backup in result.backups_created:
            assert backup.exists()
            assert ".bak." in backup.name

        # Verify backup contains original content
        cli_backups = list(temp_bundle.glob("qodercli.js.bak.*"))
        assert len(cli_backups) >= 1
        backup_content = cli_backups[0].read_text(encoding="utf-8")
        assert "navigator.userAgent" in backup_content  # original unpatched content


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------


class TestRollbackFromBackup:
    """Test rollback from backup files."""

    def test_rollback_from_backup(self, patch_instance, temp_bundle: Path):
        # First apply the patch
        apply_result = patch_instance.apply(temp_bundle)
        assert apply_result.success is True

        # Verify patched
        patched_content = (temp_bundle / "qodercli.js").read_text(encoding="utf-8")
        assert "return!1" in patched_content

        # Now rollback
        rollback_result = patch_instance.rollback(temp_bundle)
        assert rollback_result.status == PatchStatus.NOT_APPLIED
        assert len(rollback_result.files_modified) > 0

        # Verify restored to original
        restored_content = (temp_bundle / "qodercli.js").read_text(encoding="utf-8")
        assert "navigator.userAgent" in restored_content

    def test_rollback_no_backup(self, patch_instance, tmp_path: Path):
        """Rollback with no backup files should fail gracefully."""
        empty_bundle = tmp_path / "no_backups"
        empty_bundle.mkdir()
        (empty_bundle / "qodercli.js").write_text("// empty", encoding="utf-8")
        (empty_bundle / "qoder-worker-runtime.mjs").write_text("// empty", encoding="utf-8")

        result = patch_instance.rollback(empty_bundle)
        assert result.status == PatchStatus.FAILED
        assert "未找到" in result.message or "backup" in result.message.lower()


# ---------------------------------------------------------------------------
# Full lifecycle
# ---------------------------------------------------------------------------


class TestFullCycle:
    """Test the complete apply -> verify -> rollback -> verify cycle."""

    def test_full_cycle(self, patch_instance, temp_bundle: Path):
        # 1. Verify initial state: NOT_APPLIED
        status = patch_instance.check(temp_bundle)
        assert status == PatchStatus.NOT_APPLIED

        # 2. Apply the patch
        apply_result = patch_instance.apply(temp_bundle)
        assert apply_result.success is True
        assert len(apply_result.files_modified) == 2
        assert len(apply_result.backups_created) == 2

        # 3. Verify state: APPLIED
        status = patch_instance.check(temp_bundle)
        assert status == PatchStatus.APPLIED

        # 4. Apply again -> should skip (already patched)
        reapply_result = patch_instance.apply(temp_bundle)
        assert reapply_result.status == PatchStatus.APPLIED

        # 5. Rollback
        rollback_result = patch_instance.rollback(temp_bundle)
        assert rollback_result.status == PatchStatus.NOT_APPLIED
        assert len(rollback_result.files_modified) >= 1

        # 6. Verify state: NOT_APPLIED (restored)
        status = patch_instance.check(temp_bundle)
        assert status == PatchStatus.NOT_APPLIED

        # 7. Verify original content is restored
        cli_content = (temp_bundle / "qodercli.js").read_text(encoding="utf-8")
        assert "navigator.userAgent" in cli_content


# ---------------------------------------------------------------------------
# Patched pattern regex
# ---------------------------------------------------------------------------


class TestPatchedPattern:
    """Test the _PATCHED_PATTERN regex."""

    def test_matches_patched_function(self):
        assert _PATCHED_PATTERN.search("function t2(){return!1}") is not None

    def test_no_match_unpatched(self):
        assert _PATCHED_PATTERN.search("function t2(){return!0}") is None

    def test_matches_any_name(self):
        m = _PATCHED_PATTERN.search("function _abc(){return!1}")
        assert m is not None
        assert m.group(1) == "_abc"
