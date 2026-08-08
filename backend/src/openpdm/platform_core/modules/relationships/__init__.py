"""Public Relationships Platform Module contract."""

from typing import Any, Protocol

from openpdm.extension_api import ReferenceContribution, RelationshipContribution


class RelationshipsInterface(Protocol):
    """Own Relationships, References, and bounded graph traversal."""

    @staticmethod
    def persist_analysis_contribution(
        db: Any,
        *,
        provider_identity: str,
        contribution_key: str,
        source_asset_id: str,
        contribution: ReferenceContribution | RelationshipContribution,
        actor: Any,
    ) -> Any:
        """Persist one provider-owned generic contribution idempotently."""
        ...
