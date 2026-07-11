"""Public Plugins Platform Module contract."""

from typing import Protocol


class PluginsInterface(Protocol):
    """Expose the read-only plugin registry contract."""
