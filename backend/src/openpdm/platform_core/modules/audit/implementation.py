"""SQLAlchemy implementation of the Audit and Events public contract."""

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from openpdm.infrastructure.database import session_scope
from openpdm.platform_core.modules.audit import (
    AuditEventsInterface,
    AuditOutcome,
    Phase3AuditContext,
)
from openpdm.platform_core.modules.models import (
    Asset,
    AssetReference,
    AssetRelationship,
    AuditRecord,
    DomainEvent,
)
from openpdm.platform_core.request_context import get_request_id


class SqlAlchemyAuditEvents(AuditEventsInterface):
    """Persist audit outcomes without exposing storage details to business modules."""

    @staticmethod
    def _complete_context(db: Session, context: Phase3AuditContext) -> Phase3AuditContext:
        source = None
        relationship = None
        reference = None
        if context.relationship_id:
            relationship = db.scalar(
                select(AssetRelationship)
                .options(joinedload(AssetRelationship.source_asset).joinedload(Asset.project))
                .where(AssetRelationship.id == context.relationship_id)
            )
            source = relationship.source_asset if relationship else None
        elif context.reference_id:
            reference = db.scalar(
                select(AssetReference)
                .options(joinedload(AssetReference.source_asset).joinedload(Asset.project))
                .where(AssetReference.id == context.reference_id)
            )
            source = reference.source_asset if reference else None
        elif context.source_asset_id:
            source = db.scalar(
                select(Asset)
                .options(joinedload(Asset.project))
                .where(Asset.id == context.source_asset_id)
            )
        return Phase3AuditContext(
            actor_user_id=context.actor_user_id,
            event_type=context.event_type,
            resource_type=context.resource_type,
            resource_id=context.resource_id,
            project_id=context.project_id or (source.project_id if source else None),
            organization_id=context.organization_id
            or (source.project.organization_id if source else None),
            source_asset_id=context.source_asset_id or (source.id if source else None),
            target_asset_id=context.target_asset_id
            or (relationship.target_asset_id if relationship else None),
            target_uri=context.target_uri or (reference.target_uri if reference else None),
            relationship_id=context.relationship_id,
            reference_id=context.reference_id,
        )

    @staticmethod
    def _write(db: Session, context: Phase3AuditContext, outcome: AuditOutcome) -> None:
        completed = SqlAlchemyAuditEvents._complete_context(db, context)
        details: dict[str, object] = {
            "source_asset_id": completed.source_asset_id,
            "relationship_id": completed.relationship_id,
            "reference_id": completed.reference_id,
            "event_type": completed.event_type,
            "request_id": get_request_id(),
            "result": outcome.result,
            "reason": outcome.reason,
        }
        if completed.target_asset_id is not None:
            details["target_asset_id"] = completed.target_asset_id
        elif completed.target_uri is not None:
            details["target_uri"] = completed.target_uri
        db.add(
            AuditRecord(
                actor_user_id=completed.actor_user_id,
                action=f"{completed.resource_type}.{outcome.result}",
                resource_type=completed.resource_type,
                resource_id=completed.resource_id
                or completed.relationship_id
                or completed.reference_id
                or completed.source_asset_id
                or "unknown",
                organization_id=completed.organization_id,
                project_id=completed.project_id,
                details=details,
            )
        )

    def record_phase3_outcome(
        self,
        db: Session,
        *,
        context: Phase3AuditContext,
        outcome: AuditOutcome,
        independent: bool = False,
    ) -> None:
        if independent:
            with session_scope() as audit_db:
                self._write(audit_db, context, outcome)
            return
        self._write(db, context, outcome)

    def emit_domain_event(
        self,
        db: Session,
        *,
        context: Phase3AuditContext,
        payload: dict[str, object] | None = None,
    ) -> None:
        db.add(
            DomainEvent(
                event_type=context.event_type,
                resource_type=context.resource_type,
                resource_id=context.resource_id or "unknown",
                organization_id=context.organization_id,
                project_id=context.project_id,
                payload={**(payload or {}), "request_id": get_request_id()},
            )
        )
