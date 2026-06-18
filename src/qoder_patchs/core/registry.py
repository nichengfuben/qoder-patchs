"""Patch registry and auto-discovery.

Provides a central registry for all available patches, with two-layer
auto-discovery:

1. **Built-in patches** -- scanned from the ``qoder_patchs.patches`` package
   using :mod:`pkgutil`.
2. **Third-party patches** -- discovered via ``importlib.metadata`` entry
   points under the ``qoder_patchs.patches`` group.

Classes:
    PatchRegistry: Central patch storage and discovery manager.
"""

from __future__ import annotations

import importlib
import pkgutil
from importlib.metadata import entry_points
from typing import Optional

from loguru import logger

from qoder_patchs.core.patch_base import PatchBase


class PatchRegistry:
    """Central registry for patch instances.

    Maintains a mapping of patch names to their :class:`PatchBase` instances.
    Supports manual registration as well as automatic discovery of built-in
    and third-party patches.

    Example usage::

        registry = PatchRegistry()
        registry.discover_builtin()
        registry.discover_entry_points()

        patch = registry.get("win10-warning")
        if patch:
            result = patch.apply(bundle_dir)
    """

    def __init__(self) -> None:
        """Initialize an empty patch registry."""
        self._patches: dict[str, PatchBase] = {}

    def register(self, patch: PatchBase) -> None:
        """Register a patch instance.

        The patch is keyed by its ``metadata.name``. If a patch with the
        same name is already registered, a warning is logged and the
        existing entry is replaced.

        Args:
            patch: A :class:`PatchBase` instance to register.
        """
        name = patch.metadata.name
        if name in self._patches:
            logger.warning(f"Replacing already-registered patch: {name}")
        self._patches[name] = patch
        logger.debug(f"Registered patch: {name} ({patch.metadata.display_name})")

    def get(self, name: str) -> Optional[PatchBase]:
        """Look up a patch by name.

        Args:
            name: The patch name (kebab-case, e.g., ``"win10-warning"``).

        Returns:
            The :class:`PatchBase` instance, or ``None`` if not found.
        """
        return self._patches.get(name)

    def get_all(self) -> dict[str, PatchBase]:
        """Return a copy of all registered patches.

        Returns:
            A dictionary mapping patch names to :class:`PatchBase` instances.
        """
        return dict(self._patches)

    def names(self) -> list[str]:
        """Return a sorted list of all registered patch names.

        Returns:
            A sorted list of patch name strings.
        """
        return sorted(self._patches.keys())

    def discover_builtin(self) -> None:
        """Scan the ``qoder_patchs.patches`` package for built-in patches.

        Iterates over all modules in the ``qoder_patchs.patches`` package,
        skipping modules whose names start with ``_``. For each module,
        any concrete subclass of :class:`PatchBase` is instantiated and
        registered.

        Modules that fail to import are logged as warnings and skipped.
        """
        try:
            package = importlib.import_module("qoder_patchs.patches")
        except ImportError as exc:
            logger.warning(f"Cannot import qoder_patchs.patches package: {exc}")
            return

        if not hasattr(package, "__path__"):
            logger.warning("qoder_patchs.patches has no __path__, skipping builtin discovery")
            return

        for _importer, module_name, _ispkg in pkgutil.iter_modules(package.__path__):
            if module_name.startswith("_"):
                logger.debug(f"Skipping private module: {module_name}")
                continue

            full_module_name = f"qoder_patchs.patches.{module_name}"
            try:
                module = importlib.import_module(full_module_name)
            except ImportError as exc:
                logger.warning(f"Failed to import patch module {full_module_name}: {exc}")
                continue

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, PatchBase)
                    and attr is not PatchBase
                ):
                    try:
                        instance = attr()
                        self.register(instance)
                    except Exception as exc:
                        logger.warning(
                            f"Failed to instantiate {attr_name} from {full_module_name}: {exc}"
                        )

        logger.info(f"Builtin discovery complete: {len(self._patches)} patches found")

    def discover_entry_points(self, group: str = "qoder_patchs.patches") -> None:
        """Discover third-party patches via entry points.

        Scans the specified entry point group for external patch classes.
        Each entry point should reference a :class:`PatchBase` subclass
        that can be instantiated without arguments.

        Args:
            group: The entry point group name to scan. Defaults to
                ``"qoder_patchs.patches"``.

        Entry points that fail to load are logged as warnings and skipped.
        """
        try:
            eps = entry_points()
            # Python 3.12+ returns a SelectableGroups; older versions return a dict
            if hasattr(eps, "select"):
                patch_eps = eps.select(group=group)
            else:
                patch_eps = eps.get(group, [])
        except Exception as exc:
            logger.warning(f"Failed to query entry points: {exc}")
            return

        count = 0
        for ep in patch_eps:
            try:
                patch_class = ep.load()
                if not (isinstance(patch_class, type) and issubclass(patch_class, PatchBase)):
                    logger.warning(
                        f"Entry point {ep.name} does not point to a PatchBase subclass, skipping"
                    )
                    continue
                instance = patch_class()
                self.register(instance)
                count += 1
            except Exception as exc:
                logger.warning(f"Failed to load external patch '{ep.name}': {exc}")

        logger.info(f"Entry point discovery complete: {count} external patches found")
