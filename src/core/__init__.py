"""Core infrastructure - re-export key components.

This module serves as a facade for the core package, providing
convenient access to the main components:
- AppConfig: Configuration management
- PatchBase: Abstract base class for patches
- PatchRegistry: Patch discovery and registration
- PatchEngine: Patch execution engine
"""

from core.config import (
    AppConfig,
    PatchSettings,
    PathSettings,
    PersistenceSettings,
    UISettings,
)
from core.engine import PatchEngine
from core.patch_base import PatchBase, PatchMetadata, PatchResult, PatchStatus
from core.registry import PatchRegistry

__all__ = [
    "AppConfig",
    "PatchBase",
    "PatchEngine",
    "PatchMetadata",
    "PatchRegistry",
    "PatchResult",
    "PatchSettings",
    "PatchStatus",
    "PathSettings",
    "PersistenceSettings",
    "UISettings",
]
