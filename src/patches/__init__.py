"""Patch implementations for Agent CLI tools.

Each patch module contains a class inheriting from PatchBase.
Patches are automatically discovered and registered via the registry.
"""

from patches.cursor_agent import CursorAgentPatch
from patches.win10_warning import Win10WarningPatch

__all__ = ["CursorAgentPatch", "Win10WarningPatch"]
