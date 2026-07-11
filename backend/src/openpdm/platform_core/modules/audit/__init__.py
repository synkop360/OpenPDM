"""Public Audit and Events Platform Module contract."""

from dataclasses import dataclass
from typing import Any, Literal, Protocol

AuditResult = Literal["success", "failed", "denied"]


@dataclass(frozen=True, slots=True)
class Phase3AuditContext:
    actor_user_id: str
    event_type: str
    resource_type: Literal["relationship", "reference", "graph"]
    resource_id: str | None = None
    project_id: str | None = None
    organization_id: str | None = None
    source_asset_id: str | None = None
    target_asset_id: str | None = None
    target_uri: str | None = None
    relationship_id: str | None = None
    reference_id: str | None = None


@dataclass(frozen=True, slots=True)
class AuditOutcome:
    result: AuditResult
    reason: str | None = None


class AuditEventsInterface(Protocol):
    """Record Phase 3 outcomes and approved domain events."""

    def record_phase3_outcome(
        self,
        db: Any,
        *,
        context: Phase3AuditContext,
        outcome: AuditOutcome,
        independent: bool = False,
    ) -> None: ...

    def emit_domain_event(
        self,
        db: Any,
        *,
        context: Phase3AuditContext,
        payload: dict[str, object] | None = None,
    ) -> None: ...
