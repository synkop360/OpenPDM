"""Public Metadata Platform Module contract."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from openpdm.platform_core.modules.models import User


class MetadataInterface(Protocol):
    """Own generic metadata persistence and validation."""

    @staticmethod
    def authorize_target(
        db: Session, *, target_type: str, target_id: str, actor: User
    ) -> tuple[str | None, str | None]:
        """Authorize a Metadata target for a mutation without persisting it."""
        ...
