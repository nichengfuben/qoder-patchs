"""Tests for qoder_patchs.core.config module.

Covers default values, TOML loading/saving, missing file handling,
and the _strip_none_values helper.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from qoder_patchs.core.config import (
    AppConfig,
    PatchSettings,
    PathSettings,
    UISettings,
    _strip_none_values,
)


class TestDefaultValues:
    """Test that all config models have correct defaults."""

    def test_patch_settings_defaults(self):
        ps = PatchSettings()
        assert ps.auto_backup is True
        assert ps.backup_count == 3
        assert ps.dry_run_default is False
        assert ps.force_reapply is False

    def test_ui_settings_defaults(self):
        ui = UISettings()
        assert ui.theme == "blue"
        assert ui.show_banner is True
        assert ui.verbose is False
        assert ui.use_color is True

    def test_path_settings_defaults(self):
        ps = PathSettings()
        assert ps.bundle_dir is None
        assert ps.backup_dir == ".backup"
        assert ps.log_file is None

    def test_app_config_defaults(self):
        config = AppConfig()
        assert isinstance(config.patch, PatchSettings)
        assert isinstance(config.ui, UISettings)
        assert isinstance(config.paths, PathSettings)
        assert config.patch.backup_count == 3
        assert config.ui.theme == "blue"


class TestLoadFromToml:
    """Test loading configuration from TOML files."""

    def test_load_from_toml(self, temp_config: Path):
        config = AppConfig.load(temp_config)
        assert config.patch.backup_count == 5
        assert config.patch.auto_backup is True
        assert config.ui.theme == "blue"
        assert config.ui.show_banner is True
        assert config.persistence.scheduled_task is True

    def test_load_partial_toml(self, tmp_path: Path):
        """TOML with only some sections should fill rest with defaults."""
        partial = tmp_path / "partial.toml"
        partial.write_text(
            '[patch]\nbackup_count = 7\n',
            encoding="utf-8",
        )
        config = AppConfig.load(partial)
        assert config.patch.backup_count == 7
        assert config.patch.auto_backup is True  # default
        assert config.ui.theme == "blue"  # default


class TestLoadMissingFile:
    """Test behaviour when config file is missing."""

    def test_load_missing_file_returns_defaults(self, tmp_path: Path):
        missing = tmp_path / "nonexistent.toml"
        config = AppConfig.load(missing)
        assert config.patch.backup_count == 3
        assert config.ui.theme == "blue"

    def test_load_none_returns_defaults(self):
        config = AppConfig.load(None)
        assert isinstance(config, AppConfig)
        assert config.patch.auto_backup is True


class TestSaveRoundtrip:
    """Test save/load round-trip fidelity."""

    def test_save_roundtrip(self, tmp_path: Path):
        original = AppConfig()
        original.patch.backup_count = 7
        original.ui.verbose = True
        original.paths.bundle_dir = "/some/path"

        out = tmp_path / "roundtrip.toml"
        original.save(out)

        loaded = AppConfig.load(out)
        assert loaded.patch.backup_count == 7
        assert loaded.ui.verbose is True
        assert loaded.paths.bundle_dir == "/some/path"

    def test_save_creates_parent_dirs(self, tmp_path: Path):
        out = tmp_path / "sub" / "dir" / "config.toml"
        config = AppConfig()
        config.save(out)
        assert out.exists()

    def test_save_excludes_none_values(self, tmp_path: Path):
        """None values should be stripped (TOML has no null type)."""
        config = AppConfig()
        assert config.paths.bundle_dir is None
        out = tmp_path / "none_test.toml"
        config.save(out)
        content = out.read_text(encoding="utf-8")
        assert "bundle_dir" not in content


class TestStripNoneValues:
    """Test the _strip_none_values helper."""

    def test_strip_none_from_dict(self):
        result = _strip_none_values({"a": 1, "b": None, "c": "hello"})
        assert result == {"a": 1, "c": "hello"}

    def test_strip_none_nested(self):
        result = _strip_none_values({"x": {"y": None, "z": 1}})
        assert result == {"x": {"z": 1}}

    def test_strip_none_from_list(self):
        result = _strip_none_values([1, None, 3])
        # Lists preserve None items (only dict keys are stripped)
        assert result == [1, None, 3]

    def test_strip_none_scalar(self):
        assert _strip_none_values(42) == 42
        assert _strip_none_values("hello") == "hello"


class TestValidation:
    """Test Pydantic validation constraints."""

    def test_backup_count_min(self):
        with pytest.raises(Exception):
            PatchSettings(backup_count=0)

    def test_backup_count_max(self):
        with pytest.raises(Exception):
            PatchSettings(backup_count=11)

    def test_backup_count_valid(self):
        ps = PatchSettings(backup_count=5)
        assert ps.backup_count == 5
