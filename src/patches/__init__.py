"""Patch implementations for Agent CLI tools.

Each patch module contains a class inheriting from PatchBase.
Patches are automatically discovered and registered via the registry.
"""

from patches.cursor.cursor_agent import CursorAgentPatch
from patches.removeqoder_warning import RemoveQoderWarningPatch

__all__ = ["CursorAgentPatch", "RemoveQoderWarningPatch"]
