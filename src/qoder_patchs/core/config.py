"""Configuration management for qoder-patchs.

Provides Pydantic-based configuration models with TOML persistence.
Configuration is loaded from TOML files, validated, and can be saved back.

Configuration lookup priority:
    1. CLI --config argument
    2. QODER_PATCHS_CONFIG environment variable
    3. Project root config.toml
    4. User config directory (platformdirs)
    5. None (use defaults)
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Optional

import tomli_w
from loguru import logger
from pydantic import BaseModel, Field


class PatchSettings(BaseModel):
    """Patch operation settings.

    Controls backup behavior, dry-run defaults, and force-reapply policy
    for patch execution.
    """

    auto_backup: bool = Field(default=True, description="Create backup before applying patches")
    backup_count: int = Field(default=3, ge=1, le=10, description="Number of backups to retain")
    dry_run_default: bool = Field(default=False, description="Enable dry-run mode by default")
    force_reapply: bool = Field(default=False, description="Force re-apply already applied patches")


class UISettings(BaseModel):
    """User interface settings.

    Controls theme, banner display, verbosity, and color output
    for the CLI interface.
    """

    theme: str = Field(default="blue", description="UI theme name (currently only 'blue')")
    show_banner: bool = Field(default=True, description="Show ASCII art banner on startup")
    verbose: bool = Field(default=False, description="Enable verbose output mode")
    use_color: bool = Field(default=True, description="Enable colored terminal output")


class PathSettings(BaseModel):
    """Path and directory settings.

    Controls bundle directory location, backup directory, and log file
    path resolution.
    """

    bundle_dir: Optional[str] = Field(
        default=None, description="Manual bundle directory path (None = auto-detect)"
    )
    backup_dir: str = Field(
        default=".backup", description="Backup directory (relative to project root)"
    )
    log_file: Optional[str] = Field(
        default=None, description="Log file path (None = console only)"
    )


class PersistenceSettings(BaseModel):
    """Persistence mechanism settings.

    Controls Windows scheduled tasks, npm post-install hooks, and
    automatic re-patching on CLI updates.
    """

    scheduled_task: bool = Field(
        default=True, description="Create Windows scheduled task for auto-start"
    )
    npm_hooks: bool = Field(default=True, description="Install npm post-install hooks")
    on_update_repatch: bool = Field(
        default=True, description="Automatically re-apply patches after CLI update"
    )


class AppConfig(BaseModel):
    """Application configuration root model.

    Aggregates all configuration sections and provides load/save
    functionality for TOML persistence.

    Example usage::

        config = AppConfig.load(Path("config.toml"))
        config.patch.backup_count = 5
        config.save(Path("config.toml"))
    """

    patch: PatchSettings = Field(default_factory=PatchSettings)
    ui: UISettings = Field(default_factory=UISettings)
    paths: PathSettings = Field(default_factory=PathSettings)
    persistence: PersistenceSettings = Field(default_factory=PersistenceSettings)

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "AppConfig":
        """Load configuration from a TOML file with fallback to defaults.

        If ``config_path`` is ``None`` or the file does not exist, a default
        configuration is returned.  Missing sections in the TOML file are
        filled with defaults via Pydantic validation.

        Args:
            config_path: Path to the TOML configuration file.

        Returns:
            A validated ``AppConfig`` instance.

        Raises:
            pydantic.ValidationError: If the TOML data contains invalid values.
        """
        if config_path is None:
            logger.debug("No config path specified, using defaults")
            return cls()

        if not config_path.exists():
            logger.warning(f"Config file not found: {config_path}, using defaults")
            return cls()

        logger.info(f"Loading config from: {config_path}")
        try:
            with open(config_path, "rb") as f:
                data = tomllib.load(f)
        except tomllib.TOMLDecodeError as exc:
            logger.error(f"Failed to parse TOML config: {exc}")
            raise

        return cls.model_validate(data)

    def save(self, config_path: Path) -> None:
        """Save configuration to a TOML file.

        Parent directories are created automatically if they do not exist.
        ``None`` values are excluded from the output since TOML does not
        support a null type.

        Args:
            config_path: Destination path for the TOML file.
        """
        config_path.parent.mkdir(parents=True, exist_ok=True)
        data = _strip_none_values(self.model_dump())

        with open(config_path, "wb") as f:
            tomli_w.dump(data, f)

        logger.info(f"Config saved to: {config_path}")


def _strip_none_values(obj: object) -> object:
    """Recursively remove keys with ``None`` values from dicts.

    TOML has no null type, so ``None`` values must be excluded before
    serializing with ``tomli_w``.

    Args:
        obj: A dict, list, or scalar value.

    Returns:
        The input with ``None``-valued keys removed from dicts.
    """
    if isinstance(obj, dict):
        return {k: _strip_none_values(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_strip_none_values(item) for item in obj]
    return obj


def resolve_config_path(cli_arg: Optional[str] = None) -> Optional[Path]:
    """Resolve the configuration file path by priority.

    Lookup order:
        1. ``cli_arg`` -- explicit CLI ``--config`` argument
        2. ``QODER_PATCHS_CONFIG`` environment variable
        3. ``config.toml`` in the project root directory
        4. User configuration directory (via ``platformdirs``)
        5. ``None`` -- caller should use defaults

    Args:
        cli_arg: Optional path string from the ``--config`` CLI argument.

    Returns:
        A resolved ``Path`` to the config file, or ``None`` if not found.

    Raises:
        FileNotFoundError: If ``cli_arg`` is provided but the file does not exist.
    """
    # Priority 1: CLI --config argument
    if cli_arg:
        p = Path(cli_arg)
        if p.exists():
            logger.debug(f"Config resolved from CLI arg: {p}")
            return p
        raise FileNotFoundError(f"Specified config file does not exist: {cli_arg}")

    # Priority 2: QODER_PATCHS_CONFIG environment variable
    env_path = os.environ.get("QODER_PATCHS_CONFIG")
    if env_path:
        p = Path(env_path)
        if p.exists():
            logger.debug(f"Config resolved from env var: {p}")
            return p
        logger.warning(f"QODER_PATCHS_CONFIG set but file not found: {env_path}")

    # Priority 3: Project root directory (portable)
    # __file__ -> core/config.py -> core -> qoder_patchs -> src -> project root
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    local_config = project_root / "config.toml"
    if local_config.exists():
        logger.debug(f"Config resolved from project root: {local_config}")
        return local_config

    # Priority 4: User configuration directory (platformdirs)
    try:
        from platformdirs import user_config_dir

        user_config = Path(user_config_dir("qoder-patchs", "nichengfuben")) / "config.toml"
        if user_config.exists():
            logger.debug(f"Config resolved from user config dir: {user_config}")
            return user_config
    except ImportError:
        logger.debug("platformdirs not available, skipping user config dir")

    # Priority 5: Not found -> use defaults
    logger.debug("No config file found, will use defaults")
    return None
