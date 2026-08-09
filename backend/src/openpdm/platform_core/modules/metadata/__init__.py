"""Public Metadata Platform Module contract."""

from typing import Any, Protocol


class MetadataInterface(Protocol):
    """Own generic metadata persistence and validation."""

    @staticmethod
    def authorize_target(
        db: Any, *, target_type: str, target_id: str, actor: Any
    ) -> tuple[str | None, str | None]:
        """Authorize a Metadata target for a mutation without persisting it."""
        ...
