"""Tests for qoder_patchs.utils.paths module.

Covers find_bundle_dir strategies and get_project_root.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch as mock_patch

import pytest

from qoder_patchs.core.config import AppConfig
from qoder_patchs.utils.paths import (
    find_bundle_dir,
    get_backup_dir,
    get_project_root,
)


class TestFindBundleDirFromConfig:
    """Test Strategy A: config.paths.bundle_dir."""

    def test_find_bundle_dir_from_config(self, tmp_path: Path):
        # Create a valid bundle dir
        bundle = tmp_path / "my_bundle"
        bundle.mkdir()
        (bundle / "qodercli.js").write_text("// bundle", encoding="utf-8")

        config = AppConfig()
        config.paths.bundle_dir = str(bundle)

        result = find_bundle_dir(config)
        assert result == bundle

    def test_find_bundle_dir_config_invalid(self, tmp_path: Path):
        """Invalid bundle dir in config should fall through to next strategy."""
        config = AppConfig()
        config.paths.bundle_dir = str(tmp_path / "nonexistent")

        # This will try other strategies which may or may not find something
        # We just verify it doesn't crash
        result = find_bundle_dir(config)
        # Result might be None or some other directory found by later strategies
        # The key is that it doesn't raise an exception

    def test_find_bundle_dir_no_config(self):
        """Without config, should try other strategies."""
        # Should not crash
        result = find_bundle_dir(None)
        # Result might be None or a found directory


class TestFindBundleDirFromEnv:
    """Test Strategy B: QODER_PATCHS_BUNDLE environment variable."""

    def test_find_bundle_dir_from_env(self, tmp_path: Path):
        # Create a valid bundle dir
        bundle = tmp_path / "env_bundle"
        bundle.mkdir()
        (bundle / "qodercli.js").write_text("// bundle", encoding="utf-8")

        with mock_patch.dict(os.environ, {"QODER_PATCHS_BUNDLE": str(bundle)}):
            result = find_bundle_dir(None)
            assert result == bundle

    def test_find_bundle_dir_env_invalid(self, tmp_path: Path):
        """Invalid env var path should fall through."""
        with mock_patch.dict(
            os.environ,
            {"QODER_PATCHS_BUNDLE": str(tmp_path / "nonexistent")},
        ):
            # Should not crash; falls through to next strategy
            result = find_bundle_dir(None)

    def test_find_bundle_dir_env_not_set(self):
        """Without env var, should try other strategies."""
        env = os.environ.copy()
        env.pop("QODER_PATCHS_BUNDLE", None)
        with mock_patch.dict(os.environ, env, clear=True):
            result = find_bundle_dir(None)
            # Should not crash


class TestGetProjectRoot:
    """Test get_project_root returns a valid directory."""

    def test_get_project_root(self):
        root = get_project_root()
        assert root.is_dir()
        # Should contain src/ directory
        assert (root / "src").is_dir() or (root / "pyproject.toml").exists()

    def test_get_project_root_is_absolute(self):
        root = get_project_root()
        assert root.is_absolute()


class TestGetBackupDir:
    """Test get_backup_dir."""

    def test_get_backup_dir_default(self):
        """Default backup dir should be under project root."""
        backup_dir = get_backup_dir()
        assert backup_dir.is_dir()
        assert backup_dir.name == ".backup"

    def test_get_backup_dir_custom(self, tmp_path: Path):
        config = AppConfig()
        config.paths.backup_dir = str(tmp_path / "custom_backup")

        backup_dir = get_backup_dir(config)
        assert backup_dir.is_dir()
        assert "custom_backup" in str(backup_dir)


class TestFindBundleDirStrategyPriority:
    """Test that strategy A (config) takes priority over strategy B (env)."""

    def test_config_takes_priority_over_env(self, tmp_path: Path):
        config_bundle = tmp_path / "config_bundle"
        config_bundle.mkdir()
        (config_bundle / "qodercli.js").write_text("// config", encoding="utf-8")

        env_bundle = tmp_path / "env_bundle"
        env_bundle.mkdir()
        (env_bundle / "qodercli.js").write_text("// env", encoding="utf-8")

        config = AppConfig()
        config.paths.bundle_dir = str(config_bundle)

        with mock_patch.dict(os.environ, {"QODER_PATCHS_BUNDLE": str(env_bundle)}):
            result = find_bundle_dir(config)
            assert result == config_bundle
