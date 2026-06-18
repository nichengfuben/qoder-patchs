"""Patch implementations for Qoder CLI.

Each patch module contains a class inheriting from PatchBase.
Patches are automatically discovered and registered via the registry.
"""

from qoder_patchs.patches.win10_warning import Win10WarningPatch

__all__ = ["Win10WarningPatch"]
