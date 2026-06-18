"""Path resolution utilities for qoder-patchs.

Provides multi-strategy bundle directory discovery, project root resolution,
and backup directory management. The bundle directory search implements
six fallback strategies ported from the original Bash scripts.

Functions:
    find_bundle_dir: Locate the Qoder CLI bundle directory.
    get_project_root: Return the project root directory.
    get_backup_dir: Return the backup storage directory.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from qoder_patchs.core.config import AppConfig


# The npm package path for the Qoder CLI bundle (relative to npm global prefix)
_BUNDLE_PACKAGE = "@qoder-ai"
_BUNDLE_SUBDIR = "qodercli"
_BUNDLE_DIR_NAME = "bundle"


def find_bundle_dir(config: Optional["AppConfig"] = None) -> Optional[Path]:
    """Locate the Qoder CLI bundle directory using multiple fallback strategies.

    Attempts six strategies in order, returning the first valid directory
    that contains recognizable bundle files (e.g., ``qodercli.js``).

    Strategies (in order):
        A. ``config.paths.bundle_dir`` -- explicit config override
        B. ``QODER_PATCHS_BUNDLE`` environment variable
        C. ``npm prefix -g`` -- npm global installation prefix
        D. ``APPDATA``-based path -- Windows standard location
        E. Common installation paths -- well-known locations
        F. Filesystem search -- last-resort recursive find

    Args:
        config: Optional application configuration. When provided,
            Strategy A (``config.paths.bundle_dir``) is tried first.

    Returns:
        A :class:`Path` to the bundle directory, or ``None`` if no
        valid bundle directory could be found.
    """
    # Strategy A: Explicit config override
    result = _strategy_config(config)
    if result:
        return result

    # Strategy B: Environment variable
    result = _strategy_env_var()
    if result:
        return result

    # Strategy C: npm prefix -g
    result = _strategy_npm_prefix()
    if result:
        return result

    # Strategy D: APPDATA-based path
    result = _strategy_appdata()
    if result:
        return result

    # Strategy E: Common installation paths
    result = _strategy_common_paths()
    if result:
        return result

    # Strategy F: Filesystem search (last resort)
    result = _strategy_find()
    if result:
        return result

    logger.error("Bundle directory not found after trying all strategies")
    return None


def get_project_root() -> Path:
    """Return the project root directory.

    Determined by walking up from this file's location::

        paths.py -> utils/ -> qoder_patchs/ -> src/ -> project_root/

    Returns:
        Absolute :class:`Path` to the project root directory.
    """
    # __file__ -> utils/paths.py
    # .parent -> utils/
    # .parent -> qoder_patchs/
    # .parent -> src/
    # .parent -> project root
    return Path(__file__).resolve().parent.parent.parent.parent


def get_backup_dir(config: Optional["AppConfig"] = None) -> Path:
    """Return the backup storage directory.

    If ``config`` provides a custom ``paths.backup_dir``, that value is
    resolved relative to the project root. Otherwise, the default
    ``.backup`` directory under the project root is used.

    The directory is created if it does not already exist.

    Args:
        config: Optional application configuration providing a custom
            backup directory path.

    Returns:
        Absolute :class:`Path` to the backup directory (guaranteed to exist).
    """
    if config and config.paths.backup_dir:
        backup_dir = Path(config.paths.backup_dir)
        if not backup_dir.is_absolute():
            backup_dir = get_project_root() / backup_dir
    else:
        backup_dir = get_project_root() / ".backup"

    backup_dir.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Backup directory: {backup_dir}")
    return backup_dir


# ---------------------------------------------------------------------------
# Private strategy implementations
# ---------------------------------------------------------------------------


def _is_valid_bundle_dir(path: Path) -> bool:
    """Check if a path looks like a valid Qoder CLI bundle directory.

    A valid bundle directory exists and contains at least one recognizable
    file (e.g., ``qodercli.js`` or ``package.json``).

    Args:
        path: Candidate bundle directory path.

    Returns:
        ``True`` if the directory exists and contains bundle files.
    """
    if not path.is_dir():
        return False
    # Check for key bundle files
    if (path / "qodercli.js").exists():
        return True
    if (path / "package.json").exists():
        return True
    # Accept the directory even without specific files (may be a newer version)
    return any(path.iterdir()) if path.is_dir() else False


def _strategy_config(config: Optional["AppConfig"]) -> Optional[Path]:
    """Strategy A: Use config.paths.bundle_dir if set."""
    if config is None:
        return None
    if config.paths.bundle_dir is None:
        logger.debug("Strategy A: config.paths.bundle_dir not set, skipping")
        return None

    path = Path(config.paths.bundle_dir)
    if _is_valid_bundle_dir(path):
        logger.info(f"Strategy A: Bundle dir from config: {path}")
        return path

    logger.warning(f"Strategy A: Config bundle dir invalid: {path}")
    return None


def _strategy_env_var() -> Optional[Path]:
    """Strategy B: Use QODER_PATCHS_BUNDLE environment variable."""
    env_path = os.environ.get("QODER_PATCHS_BUNDLE")
    if not env_path:
        logger.debug("Strategy B: QODER_PATCHS_BUNDLE not set, skipping")
        return None

    path = Path(env_path)
    if _is_valid_bundle_dir(path):
        logger.info(f"Strategy B: Bundle dir from env var: {path}")
        return path

    logger.warning(f"Strategy B: Env var bundle dir invalid: {path}")
    return None


def _strategy_npm_prefix() -> Optional[Path]:
    """Strategy C: Use ``npm prefix -g`` to find the global npm directory."""
    import shutil

    npm_exe = shutil.which("npm")
    if not npm_exe:
        logger.debug("Strategy C: npm not found on PATH, skipping")
        return None

    try:
        result = subprocess.run(
            ["npm", "prefix", "-g"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            logger.debug(f"Strategy C: npm prefix -g failed (rc={result.returncode})")
            return None

        npm_prefix = result.stdout.strip()
        if not npm_prefix:
            logger.debug("Strategy C: npm prefix -g returned empty string")
            return None

        bundle_path = Path(npm_prefix) / "node_modules" / _BUNDLE_PACKAGE / _BUNDLE_SUBDIR / _BUNDLE_DIR_NAME
        if _is_valid_bundle_dir(bundle_path):
            logger.info(f"Strategy C: Bundle dir from npm prefix: {bundle_path}")
            return bundle_path

        # Also try without the /bundle subdirectory
        alt_path = Path(npm_prefix) / "node_modules" / _BUNDLE_PACKAGE / _BUNDLE_SUBDIR
        if _is_valid_bundle_dir(alt_path):
            logger.info(f"Strategy C: Bundle dir from npm prefix (alt): {alt_path}")
            return alt_path

        logger.debug(f"Strategy C: npm bundle dir not found at: {bundle_path}")
        return None

    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.debug(f"Strategy C: npm prefix -g error: {exc}")
        return None


def _strategy_appdata() -> Optional[Path]:
    """Strategy D: Use APPDATA-based path (Windows standard location)."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        logger.debug("Strategy D: APPDATA not set, skipping")
        return None

    bundle_path = (
        Path(appdata)
        / "npm"
        / "node_modules"
        / _BUNDLE_PACKAGE
        / _BUNDLE_SUBDIR
        / _BUNDLE_DIR_NAME
    )
    if _is_valid_bundle_dir(bundle_path):
        logger.info(f"Strategy D: Bundle dir from APPDATA: {bundle_path}")
        return bundle_path

    # Also try without /bundle subdirectory
    alt_path = (
        Path(appdata)
        / "npm"
        / "node_modules"
        / _BUNDLE_PACKAGE
        / _BUNDLE_SUBDIR
    )
    if _is_valid_bundle_dir(alt_path):
        logger.info(f"Strategy D: Bundle dir from APPDATA (alt): {alt_path}")
        return alt_path

    logger.debug(f"Strategy D: APPDATA bundle dir not found at: {bundle_path}")
    return None


def _strategy_common_paths() -> Optional[Path]:
    """Strategy E: Check common installation paths."""
    home = Path.home()

    candidates: list[Path] = []

    # Windows common paths
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / "npm" / "node_modules" / _BUNDLE_PACKAGE / _BUNDLE_SUBDIR / _BUNDLE_DIR_NAME)

    # Program Files (npm global install via nvm-windows or similar)
    program_files = os.environ.get("PROGRAMFILES")
    if program_files:
        candidates.append(
            Path(program_files) / "nodejs" / "node_modules" / _BUNDLE_PACKAGE / _BUNDLE_SUBDIR / _BUNDLE_DIR_NAME
        )

    # Home directory based (nvm, fnm, volta, etc.)
    candidates.extend([
        home / "AppData" / "Roaming" / "npm" / "node_modules" / _BUNDLE_PACKAGE / _BUNDLE_SUBDIR / _BUNDLE_DIR_NAME,
        home / ".npm-global" / "node_modules" / _BUNDLE_PACKAGE / _BUNDLE_SUBDIR / _BUNDLE_DIR_NAME,
        home / ".fnm" / "node_modules" / _BUNDLE_PACKAGE / _BUNDLE_SUBDIR / _BUNDLE_DIR_NAME,
        home / ".volta" / "tools" / "image" / "packages" / _BUNDLE_PACKAGE / _BUNDLE_SUBDIR / _BUNDLE_DIR_NAME,
    ])

    # Linux / macOS common paths
    candidates.extend([
        Path("/usr/local/lib/node_modules") / _BUNDLE_PACKAGE / _BUNDLE_SUBDIR / _BUNDLE_DIR_NAME,
        Path("/usr/lib/node_modules") / _BUNDLE_PACKAGE / _BUNDLE_SUBDIR / _BUNDLE_DIR_NAME,
        home / ".nvm" / "versions" / "node" / "*" / "lib" / "node_modules" / _BUNDLE_PACKAGE / _BUNDLE_SUBDIR / _BUNDLE_DIR_NAME,
    ])

    for candidate in candidates:
        # Handle glob patterns (e.g., nvm versions/node/*)
        if "*" in str(candidate):
            # Find the glob component and expand
            parts = candidate.parts
            for i, part in enumerate(parts):
                if "*" in part:
                    glob_parent = Path(*parts[:i + 1])
                    if glob_parent.exists():
                        for match in glob_parent.parent.glob(part):
                            remaining = Path(*parts[i + 1:])
                            resolved = match / remaining
                            if _is_valid_bundle_dir(resolved):
                                logger.info(f"Strategy E: Bundle dir from common path: {resolved}")
                                return resolved
            continue

        if _is_valid_bundle_dir(candidate):
            logger.info(f"Strategy E: Bundle dir from common path: {candidate}")
            return candidate

    logger.debug("Strategy E: No valid bundle dir found in common paths")
    return None


def _strategy_find() -> Optional[Path]:
    """Strategy F: Last-resort filesystem search for the bundle directory.

    Searches a limited set of root directories for ``qodercli.js`` files
    to locate the bundle. This is slow and only used as a final fallback.
    """
    logger.debug("Strategy F: Starting last-resort filesystem search")

    search_roots: list[Path] = []

    # Determine search roots based on platform
    appdata = os.environ.get("APPDATA")
    if appdata:
        search_roots.append(Path(appdata))

    home = Path.home()
    search_roots.extend([
        home / ".npm-global",
        home / ".fnm",
        home / ".volta",
        home / ".nvm",
    ])

    # Also search Program Files on Windows
    for env_var in ("PROGRAMFILES", "LOCALAPPDATA"):
        val = os.environ.get(env_var)
        if val:
            search_roots.append(Path(val))

    for root in search_roots:
        if not root.is_dir():
            continue

        try:
            # Search for qodercli.js with limited depth
            for match in root.rglob("qodercli.js"):
                bundle_dir = match.parent
                if bundle_dir.name == _BUNDLE_DIR_NAME or bundle_dir.name == _BUNDLE_SUBDIR:
                    logger.info(f"Strategy F: Bundle dir found via search: {bundle_dir}")
                    return bundle_dir
        except (PermissionError, OSError) as exc:
            logger.debug(f"Strategy F: Permission error searching {root}: {exc}")
            continue

    logger.debug("Strategy F: Filesystem search found nothing")
    return None
