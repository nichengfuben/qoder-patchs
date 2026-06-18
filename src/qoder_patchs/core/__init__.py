"""Core infrastructure - re-export key components.

This module serves as a facade for the core package, providing
convenient access to the main components:
- AppConfig: Configuration management
- PatchBase: Abstract base class for patches
- PatchRegistry: Patch discovery and registration
- PatchEngine: Patch execution engine
"""

from qoder_patchs.core.config import (
    AppConfig,
    PatchSettings,
    PathSettings,
    PersistenceSettings,
    UISettings,
)
from qoder_patchs.core.engine import PatchEngine
from qoder_patchs.core.patch_base import PatchBase, PatchMetadata, PatchResult, PatchStatus
from qoder_patchs.core.registry import PatchRegistry

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
