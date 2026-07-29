"""Public Relationships Platform Module contract."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from openpdm.extension_api import ReferenceContribution, RelationshipContribution
    from openpdm.platform_core.modules.models import AssetReference, AssetRelationship, User


class RelationshipsInterface(Protocol):
    """Own Relationships, References, and bounded graph traversal."""

    @staticmethod
    def persist_analysis_contribution(
        db: Session,
        *,
        provider_identity: str,
        contribution_key: str,
        source_asset_id: str,
        contribution: ReferenceContribution | RelationshipContribution,
        actor: User,
    ) -> AssetReference | AssetRelationship:
        """Persist one provider-owned generic contribution idempotently."""
        ...
