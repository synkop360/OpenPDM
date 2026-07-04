"""Shared contracts for Platform Module boundary declarations."""

from typing import Protocol


class PublicModuleInterface(Protocol):
    """Marker protocol for public Platform Module interfaces."""

    @property
    def module_name(self) -> str:
        """Return the public Platform Module name."""
        ...
