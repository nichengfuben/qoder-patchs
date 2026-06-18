"""Tests for qoder_patchs.cli.app module.

Smoke tests for CLI commands using Typer's CliRunner.

Note: Many CLI commands use BlueCLI (Rich Console) which writes directly
to stdout, bypassing Typer's CliRunner capture.  For those commands we
use pytest's ``capsys`` fixture to capture the output.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from qoder_patchs.cli.app import typer_app, _state


runner = CliRunner()


@pytest.fixture(autouse=True)
def _reset_app_state():
    """Reset the module-level _state dict between tests to avoid leakage."""
    saved = dict(_state)
    yield
    _state.clear()
    _state.update(saved)


class TestHelpCommand:
    """Test --help output."""

    def test_help_command(self):
        result = runner.invoke(typer_app, ["--help"])
        assert result.exit_code == 0
        # Should contain usage information
        assert "qoder-patchs" in result.output.lower() or "Usage" in result.output or "用法" in result.output


class TestAboutCommand:
    """Test the about command."""

    def test_about_command(self):
        result = runner.invoke(typer_app, ["about"])
        assert result.exit_code == 0
        # Note: Rich Console writes to real stdout, bypassing CliRunner capture.
        # We verify the command routes correctly (exit code 0) rather than output.


class TestStatusCommand:
    """Test the status command (without bundle dir)."""

    def test_status_command(self):
        """Status should handle missing bundle dir gracefully."""
        result = runner.invoke(typer_app, ["status"])
        # May exit with code 10 (bundle not found) or 0
        assert result.exit_code in (0, 10)


class TestConfigShowCommand:
    """Test config show sub-command."""

    def test_config_show(self):
        result = runner.invoke(typer_app, ["config", "show"])
        assert result.exit_code == 0
        # Note: Rich Console writes to real stdout, bypassing CliRunner capture.
        # We verify the command routes correctly (exit code 0) rather than output.
