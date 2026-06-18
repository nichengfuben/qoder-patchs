"""Global pytest fixtures for qoder-patchs tests.

Provides shared fixtures for mock bundle directories, configuration,
and pre-patched bundles used across all test modules.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch as _mock_patch

import pytest

from qoder_patchs.core.config import AppConfig


# ---------------------------------------------------------------------------
# Autouse: prevent Windows stdout wrapping during tests
# ---------------------------------------------------------------------------
# On Windows, get_console() wraps sys.stdout.buffer in a TextIOWrapper,
# which conflicts with pytest's output capture and causes
# "I/O operation on closed file" errors.  This autouse fixture patches
# the helper to always return the plain sys.stdout during tests.

@pytest.fixture(autouse=True)
def _disable_windows_stdout_wrapping():
    """Patch _get_utf8_stdout to return plain sys.stdout (no wrapping)."""
    with _mock_patch(
        "qoder_patchs.cli.theme._get_utf8_stdout",
        return_value=sys.stdout,
    ):
        yield


# ---------------------------------------------------------------------------
# Simulated bundle content
# ---------------------------------------------------------------------------

# Content that mimics the real Qoder CLI bundle files.
# Contains the ``isWindows10`` export mapping pointing to an obfuscated
# function name (``t2``), and a standard function body.

_QODERCLI_JS_UNPATCHED = """\
// Qoder CLI main entry point (simulated for testing)
var __qoder_modules = {};
function t1(){return!0}
function t2(){var e=navigator.userAgent;return e.indexOf("Windows NT 10.0")>-1}
function t3(){return"qoder"}
var exportMapping = {
  isWindows10:()=>t2,
  isLinux:()=>t1,
  getAppName:()=>t3
};
function startCli(){
  var warnings=[];
  if(t2()&&warnings.push({id:"windows-10",msg:"Windows 10 detected"})){
    console.warn("Windows 10 warning");
  }
  console.log("CLI started");
}
startCli();
"""

_WORKER_RUNTIME_MJS_UNPATCHED = """\
// Qoder Worker Runtime (simulated for testing)
function w1(){return!0}
function w2(){var e=navigator.userAgent;return e.indexOf("Windows NT 10.0")>-1}
function w3(){return"worker"}
var workerExports = {
  isWindows10:()=>w2,
  isReady:()=>w1,
  getName:()=>w3
};
export default workerExports;
"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def temp_bundle(tmp_path: Path) -> Path:
    """Create a mock bundle directory with unpatched simulated bundle files.

    The directory contains:
    - qodercli.js  (with ``isWindows10:()=>t2`` export mapping)
    - qoder-worker-runtime.mjs  (with ``isWindows10:()=>w2`` export mapping)

    Returns:
        Path to the temporary bundle directory.
    """
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()

    (bundle_dir / "qodercli.js").write_text(_QODERCLI_JS_UNPATCHED, encoding="utf-8")
    (bundle_dir / "qoder-worker-runtime.mjs").write_text(
        _WORKER_RUNTIME_MJS_UNPATCHED, encoding="utf-8"
    )

    return bundle_dir


@pytest.fixture()
def patched_bundle(tmp_path: Path) -> Path:
    """Create a mock bundle directory with patches already applied.

    Both files contain the ``function XX(){return!1}`` pattern that
    the Win10WarningPatch.check() method recognises as "applied".

    Returns:
        Path to the temporary bundle directory.
    """
    bundle_dir = tmp_path / "bundle_patched"
    bundle_dir.mkdir()

    patched_cli = _QODERCLI_JS_UNPATCHED.replace(
        'function t2(){var e=navigator.userAgent;return e.indexOf("Windows NT 10.0")>-1}',
        "function t2(){return!1}",
    )
    patched_worker = _WORKER_RUNTIME_MJS_UNPATCHED.replace(
        'function w2(){var e=navigator.userAgent;return e.indexOf("Windows NT 10.0")>-1}',
        "function w2(){return!1}",
    )

    (bundle_dir / "qodercli.js").write_text(patched_cli, encoding="utf-8")
    (bundle_dir / "qoder-worker-runtime.mjs").write_text(patched_worker, encoding="utf-8")

    return bundle_dir


@pytest.fixture()
def app_config() -> AppConfig:
    """Return a default AppConfig instance for testing.

    Returns:
        A fresh :class:`AppConfig` with all default values.
    """
    return AppConfig()


@pytest.fixture()
def temp_config(tmp_path: Path) -> Path:
    """Create a temporary config.toml file with sample values.

    Returns:
        Path to the temporary TOML configuration file.
    """
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """\
[patch]
auto_backup = true
backup_count = 5
dry_run_default = false
force_reapply = false

[ui]
theme = "blue"
show_banner = true
verbose = false
use_color = true

[paths]
backup_dir = ".backup"

[persistence]
scheduled_task = true
npm_hooks = true
on_update_repatch = true
""",
        encoding="utf-8",
    )
    return config_path
