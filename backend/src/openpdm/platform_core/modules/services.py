"""Platform Module public services for the Phase 1 Core Platform MVP."""

from __future__ import annotations

import base64
import hashlib
import secrets
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import wraps
from pathlib import PurePath
from typing import Literal, TypeVar
from typing import cast as type_cast

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import String, and_, cast, delete, func, literal, or_, select
from sqlalchemy.orm import Session, joinedload

from openpdm.extension_api import ValidatedPluginPackage
from openpdm.infrastructure.blob_storage import BlobStorage
from openpdm.infrastructure.plugin_packages import PluginPackageStorage
from openpdm.infrastructure.plugin_secrets import PluginSecretCipher
from openpdm.infrastructure.settings import Settings
from openpdm.platform_core.modules.audit import (
    AuditEventsInterface,
    AuditOutcome,
    Phase3AuditContext,
)
from openpdm.platform_core.modules.models import (
    Asset,
    AssetCollaborationLock,
    AssetReference,
    AssetRelationship,
    AuditRecord,
    Blob,
    DomainEvent,
    MetadataEntry,
    NotificationRecord,
    Organization,
    OrganizationMembership,
    PluginConfiguration,
    PluginEventDelivery,
    PluginRecord,
    Project,
    ProjectAssetView,
    ProjectMembership,
    Representation,
    Revision,
    SessionToken,
    User,
)
from openpdm.platform_core.pagination import PageResult, paginate
from openpdm.platform_core.public import PluginEventDeliveryView
from openpdm.platform_core.request_context import get_request_id

ORG_ROLE_PRIORITY = {"Owner": 4, "Maintainer": 3, "Contributor": 2, "Viewer": 1}
PROJECT_ROLE_PRIORITY = ORG_ROLE_PRIORITY
PROJECT_PERMISSION_ROLES = {
    "read_project": {"Owner", "Maintainer", "Contributor", "Viewer"},
    "manage_project": {"Owner", "Maintainer"},
    "create_asset": {"Owner", "Maintainer", "Contributor"},
    "update_asset": {"Owner", "Maintainer", "Contributor"},
    "delete_asset": {"Owner", "Maintainer"},
    "create_revision": {"Owner", "Maintainer", "Contributor"},
    "manage_members": {"Owner", "Maintainer"},
}
ALLOWED_STATUSES = {"draft", "active", "archived"}
ASSET_PAGE_SORTS = {"created_at", "updated_at", "name", "status"}
ASSET_VIEW_COLUMNS = {
    "name",
    "description",
    "status",
    "created_at",
    "updated_at",
    "created_by_user_id",
}
MEMBERSHIP_PAGE_SORTS = {"created_at", "role"}
NOTIFICATION_PAGE_SORTS = {"created_at", "event_type"}
PLUGIN_PAGE_SORTS = {"created_at", "updated_at", "name", "lifecycle_state"}
ALLOWED_METADATA_TYPES = {"string", "number", "boolean", "date", "json"}
ALLOWED_PLUGIN_TYPES = {"official", "community"}
PLUGIN_LIFECYCLE_STATES = {
    "discovered",
    "installed",
    "disabled",
    "starting",
    "running",
    "failed",
    "incompatible",
}
COLLABORATION_STATES = {"available", "locked", "stale_lock"}
FORCE_UNLOCK_ROLES = {"Owner", "Maintainer"}
LOCK_OWNER_WRITE_ROLES = {"Owner", "Maintainer", "Contributor"}
ALLOWED_RELATIONSHIP_TYPES = {
    "depends_on",
    "references",
    "derived_from",
    "generates",
    "supersedes",
    "related_to",
}
RELATIONSHIP_DIRECTION = "directed"
DEFAULT_GRAPH_DEPTH = 3
MAX_GRAPH_DEPTH = 10
GRAPH_DIRECTIONS = {"incoming", "outgoing", "both"}
METADATA_TARGET_FIELDS = {
    "asset": "asset_id",
    "revision": "revision_id",
    "representation": "representation_id",
}
TIMELINE_EVENT_MAP = {
    "asset.created": "AssetCreated",
    "asset.checked_out": "AssetLocked",
    "asset.unlocked": "AssetUnlocked",
    "asset.force_unlocked": "ForceUnlocked",
    "revision.created": "RevisionCreated",
    "asset.checked_in": "CheckInCompleted",
    "collaboration.conflict_detected": "ConflictDetected",
}
_AUDIT_EVENTS: AuditEventsInterface | None = None
F = TypeVar("F", bound=Callable[..., object])


def utc_now() -> datetime:
    """Return the current UTC time."""
    return datetime.now(UTC)


def configure_audit_events(audit_events: AuditEventsInterface) -> None:
    """Inject the Audit/Events public interface into Platform Module implementations."""
    global _AUDIT_EVENTS
    _AUDIT_EVENTS = audit_events


def audited_phase3_mutation(
    *,
    event_type: str,
    resource_type: Literal["relationship", "reference", "graph"],
    relationship_id: str | None = None,
    reference_id: str | None = None,
    source_asset_id: str | None = None,
    target_asset_id: str | None = None,
    target_uri: str | None = None,
) -> Callable[[F], F]:
    """Persist failures and denials independently from a Phase 3 mutation."""

    def decorate(function: F) -> F:
        @wraps(function)
        def wrapped(*args: object, **kwargs: object) -> object:
            db = type_cast(Session, args[0] if args else kwargs["db"])
            actor = kwargs["actor"]
            try:
                return function(*args, **kwargs)
            except Exception as exc:
                db.rollback()
                if _AUDIT_EVENTS is not None:
                    denied = (
                        isinstance(exc, HTTPException)
                        and exc.status_code == status.HTTP_403_FORBIDDEN
                    )
                    reason = (
                        "Permission denied."
                        if denied
                        else (
                            str(exc.detail)
                            if isinstance(exc, HTTPException)
                            else "Persistence failure."
                        )
                    )
                    context = Phase3AuditContext(
                        actor_user_id=type_cast(User, actor).id,
                        event_type=event_type,
                        resource_type=resource_type,
                        relationship_id=type_cast(str | None, kwargs.get(relationship_id))
                        if relationship_id
                        else None,
                        reference_id=type_cast(str | None, kwargs.get(reference_id))
                        if reference_id
                        else None,
                        source_asset_id=type_cast(str | None, kwargs.get(source_asset_id))
                        if source_asset_id
                        else None,
                        target_asset_id=type_cast(str | None, kwargs.get(target_asset_id))
                        if target_asset_id
                        else None,
                        target_uri=type_cast(str | None, kwargs.get(target_uri))
                        if target_uri
                        else None,
                    )
                    _AUDIT_EVENTS.record_phase3_outcome(
                        db,
                        context=context,
                        outcome=AuditOutcome("denied" if denied else "failed", reason),
                        independent=True,
                    )
                raise

        return type_cast(F, wrapped)

    return decorate


def audited_phase3_read(
    *,
    resource_type: Literal["relationship", "reference", "graph"],
    source_asset_id: str | None = None,
    relationship_id: str | None = None,
    reference_id: str | None = None,
) -> Callable[[F], F]:
    """Audit security-sensitive Phase 3 read denials without leaking resource details."""

    def decorate(function: F) -> F:
        @wraps(function)
        def wrapped(*args: object, **kwargs: object) -> object:
            db = type_cast(Session, args[0] if args else kwargs["db"])
            actor = type_cast(User, kwargs["actor"])
            try:
                return function(*args, **kwargs)
            except HTTPException as exc:
                if exc.status_code == status.HTTP_403_FORBIDDEN and _AUDIT_EVENTS is not None:
                    db.rollback()
                    _AUDIT_EVENTS.record_phase3_outcome(
                        db,
                        context=Phase3AuditContext(
                            actor_user_id=actor.id,
                            event_type="GraphQueryExecuted",
                            resource_type=resource_type,
                            source_asset_id=type_cast(str | None, kwargs.get(source_asset_id))
                            if source_asset_id
                            else None,
                            relationship_id=type_cast(str | None, kwargs.get(relationship_id))
                            if relationship_id
                            else None,
                            reference_id=type_cast(str | None, kwargs.get(reference_id))
                            if reference_id
                            else None,
                        ),
                        outcome=AuditOutcome("denied", "Permission denied."),
                        independent=True,
                    )
                raise

        return type_cast(F, wrapped)

    return decorate


def hash_password(password: str) -> str:
    """Return a salted password hash."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"{base64.b64encode(salt).decode()}:{base64.b64encode(digest).decode()}"


def verify_password(password: str, password_hash: str) -> bool:
    """Check a password against the stored hash."""
    salt_text, digest_text = password_hash.split(":", maxsplit=1)
    salt = base64.b64decode(salt_text.encode())
    expected = base64.b64decode(digest_text.encode())
    actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return secrets.compare_digest(actual, expected)


def new_session_token() -> str:
    """Return a new opaque bearer token."""
    return secrets.token_urlsafe(32)


def require(condition: bool, message: str, code: int = status.HTTP_400_BAD_REQUEST) -> None:
    """Raise an HTTPException when a precondition fails."""
    if not condition:
        raise HTTPException(status_code=code, detail=message)


def validate_page_sort(sort: str, allowed: set[str]) -> None:
    require(sort in allowed, "Unsupported collection sort key.")


def collaboration_error(
    *,
    code: str,
    message: str,
    status_code: int = status.HTTP_409_CONFLICT,
    context: dict[str, object] | None = None,
) -> HTTPException:
    """Return a standardized collaboration error."""
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, "context": context or {}},
    )


def collaboration_recovery_context(
    code: str, *, details: dict[str, object] | None = None
) -> dict[str, object]:
    """Return generic recovery guidance for collaboration API errors."""
    guidance: dict[str, dict[str, object]] = {
        "asset_locked": {
            "recovery_action": "wait_or_coordinate",
            "user_guidance": "Wait for the current lock owner to release the Asset or ask a Maintainer or Owner to coordinate.",
            "can_retry": True,
            "should_refresh": True,
        },
        "checkin_without_lock": {
            "recovery_action": "checkout_asset",
            "user_guidance": "Check out the Asset before trying to check in changes.",
            "can_retry": True,
            "should_refresh": True,
        },
        "checkin_by_non_owner": {
            "recovery_action": "lock_owner_only",
            "user_guidance": "Only the current lock owner can check in changes for this Asset.",
            "can_retry": False,
            "should_refresh": True,
        },
        "unlock_not_allowed": {
            "recovery_action": "lock_owner_only",
            "user_guidance": "Only the current lock owner can unlock this Asset unless a Maintainer or Owner force-unlocks it.",
            "can_retry": False,
            "should_refresh": True,
        },
        "asset_archived": {
            "recovery_action": "read_only",
            "user_guidance": "This Asset is archived and must remain read-only in the collaboration flow.",
            "can_retry": False,
            "should_refresh": True,
        },
        "no_active_lock": {
            "recovery_action": "refresh_state",
            "user_guidance": "Refresh the collaboration state before retrying this action.",
            "can_retry": True,
            "should_refresh": True,
        },
        "checkin_comment_required": {
            "recovery_action": "provide_comment",
            "user_guidance": "Add a revision comment before retrying the check-in.",
            "can_retry": True,
            "should_refresh": False,
        },
        "representation_blob_not_found": {
            "recovery_action": "reupload_blob",
            "user_guidance": "Upload the file again and retry the check-in with a valid Blob.",
            "can_retry": True,
            "should_refresh": False,
        },
    }
    return {**guidance.get(code, {}), **(details or {})}


def get_user_by_email(db: Session, email: str) -> User | None:
    """Return a user by email."""
    return db.scalar(select(User).where(User.email == email.lower().strip()))


def get_user_or_404(db: Session, user_id: str) -> User:
    """Return a user or raise 404."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return user


def record_audit(
    db: Session,
    *,
    actor_user_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str,
    organization_id: str | None = None,
    project_id: str | None = None,
    details: dict[str, object] | None = None,
) -> None:
    """Record a significant audit event."""
    payload = dict(details or {})
    request_id = get_request_id()
    if request_id is not None:
        payload.setdefault("request_id", request_id)
    if resource_type in {"relationship", "reference"}:
        event_types = {
            "relationship.created": "RelationshipCreated",
            "relationship.deleted": "RelationshipDeleted",
            "relationship.metadata.updated": "RelationshipMetadataUpdated",
            "relationship.cycle_detected": "RelationshipCycleDetected",
            "relationship.create_failed": "RelationshipCreated",
            "relationship.permission_denied": "RelationshipCreated",
            "reference.created": "ReferenceCreated",
            "reference.deleted": "ReferenceDeleted",
            "reference.resolved": "ReferenceResolved",
        }
        payload.setdefault("event_type", event_types.get(action, action))
        payload.setdefault(f"{resource_type}_id", resource_id)
        payload.setdefault("result", "success")
        payload.setdefault("reason", None)
    db.add(
        AuditRecord(
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            organization_id=organization_id,
            project_id=project_id,
            details=payload,
        )
    )


def emit_event(
    db: Session,
    *,
    event_type: str,
    resource_type: str,
    resource_id: str,
    organization_id: str | None = None,
    project_id: str | None = None,
    payload: dict[str, object] | None = None,
) -> None:
    """Record a domain event for a significant action."""
    event_payload = dict(payload or {})
    request_id = get_request_id()
    if request_id is not None:
        event_payload.setdefault("request_id", request_id)
    event = DomainEvent(
        event_type=event_type,
        resource_type=resource_type,
        resource_id=resource_id,
        organization_id=organization_id,
        project_id=project_id,
        payload=event_payload,
    )
    db.add(event)
    db.flush()
    candidates = db.scalars(
        select(PluginRecord).where(
            and_(
                PluginRecord.enabled.is_(True),
                PluginRecord.lifecycle_state == "running",
            )
        )
    )
    for plugin in candidates:
        if (
            "event_handler" not in plugin.capabilities
            or event_type not in plugin.event_subscriptions
        ):
            continue
        db.add(
            PluginEventDelivery(
                plugin_id=plugin.id,
                domain_event_id=event.id,
                event_type=event_type,
                payload={
                    "event_id": event.id,
                    "event_type": event_type,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "organization_id": organization_id,
                    "project_id": project_id,
                    "payload": event_payload,
                    "occurred_at": event.emitted_at.isoformat(),
                },
            )
        )


def _membership_role(
    db: Session,
    *,
    model: type[OrganizationMembership] | type[ProjectMembership],
    field_name: str,
    parent_id: str,
    user_id: str,
) -> str | None:
    field = getattr(model, field_name)
    membership = db.scalar(select(model).where(and_(field == parent_id, model.user_id == user_id)))
    return membership.role if membership else None


class AuthModule:
    """Public auth module service."""

    @staticmethod
    def register_user(db: Session, *, email: str, display_name: str, password: str) -> User:
        require(
            email and password and display_name, "Email, display name and password are required."
        )
        require(
            get_user_by_email(db, email) is None,
            "Email is already registered.",
            status.HTTP_409_CONFLICT,
        )
        first_user = db.scalar(select(func.count()).select_from(User)) == 0
        user = User(
            email=email.lower().strip(),
            display_name=display_name.strip(),
            password_hash=hash_password(password),
            is_platform_admin=first_user,
        )
        db.add(user)
        db.flush()
        record_audit(
            db,
            actor_user_id=user.id,
            action="user.registered",
            resource_type="user",
            resource_id=user.id,
        )
        emit_event(db, event_type="user.registered", resource_type="user", resource_id=user.id)
        if first_user:
            record_audit(
                db,
                actor_user_id=user.id,
                action="platform_administrator.bootstrapped",
                resource_type="user",
                resource_id=user.id,
            )
            emit_event(
                db,
                event_type="platform_administrator.bootstrapped",
                resource_type="user",
                resource_id=user.id,
            )
        return user

    @staticmethod
    def sign_in(db: Session, *, email: str, password: str) -> tuple[User, SessionToken]:
        user = get_user_by_email(db, email)
        require(user is not None, "Invalid credentials.", status.HTTP_401_UNAUTHORIZED)
        require(user.is_active, "User is inactive.", status.HTTP_403_FORBIDDEN)
        require(
            verify_password(password, user.password_hash),
            "Invalid credentials.",
            status.HTTP_401_UNAUTHORIZED,
        )
        session_token = SessionToken(token=new_session_token(), user_id=user.id)
        db.add(session_token)
        db.flush()
        record_audit(
            db,
            actor_user_id=user.id,
            action="session.created",
            resource_type="session",
            resource_id=session_token.id,
        )
        emit_event(
            db, event_type="session.created", resource_type="session", resource_id=session_token.id
        )
        return user, session_token

    @staticmethod
    def set_platform_administrator(
        db: Session, *, target_user_id: str, enabled: bool, actor: User
    ) -> User:
        require(
            actor.is_active and actor.is_platform_admin,
            "Platform Administrator authority is required.",
            status.HTTP_403_FORBIDDEN,
        )
        target = get_user_or_404(db, target_user_id)
        if not enabled and target.is_platform_admin:
            administrator_count = db.scalar(
                select(func.count())
                .select_from(User)
                .where(and_(User.is_active.is_(True), User.is_platform_admin.is_(True)))
            )
            require(
                administrator_count is not None and administrator_count > 1,
                "The deployment must retain at least one active Platform Administrator.",
                status.HTTP_409_CONFLICT,
            )
        previous = target.is_platform_admin
        target.is_platform_admin = enabled
        record_audit(
            db,
            actor_user_id=actor.id,
            action="platform_administrator.updated",
            resource_type="user",
            resource_id=target.id,
            details={"previous": previous, "enabled": enabled},
        )
        emit_event(
            db,
            event_type="platform_administrator.updated",
            resource_type="user",
            resource_id=target.id,
            payload={"previous": previous, "enabled": enabled},
        )
        return target

    @staticmethod
    def get_session(db: Session, token: str) -> SessionToken:
        statement = (
            select(SessionToken)
            .options(joinedload(SessionToken.user))
            .where(SessionToken.token == token)
        )
        session_token = db.scalar(statement)
        require(session_token is not None, "Invalid session.", status.HTTP_401_UNAUTHORIZED)
        require(
            session_token.revoked_at is None,
            "Session has been revoked.",
            status.HTTP_401_UNAUTHORIZED,
        )
        require(session_token.user.is_active, "User is inactive.", status.HTTP_403_FORBIDDEN)
        return session_token

    @staticmethod
    def get_session_by_id(db: Session, *, session_id: str) -> SessionToken:
        """Return a session through the Authentication Platform Module boundary."""
        session_token = db.get(SessionToken, session_id)
        if session_token is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
        return session_token

    @staticmethod
    def revoke_session(
        db: Session, *, session_token: SessionToken, actor_user_id: str
    ) -> SessionToken:
        require(
            session_token.user_id == actor_user_id,
            "Users can revoke only their own sessions.",
            status.HTTP_403_FORBIDDEN,
        )
        if session_token.revoked_at is None:
            session_token.revoked_at = utc_now()
            record_audit(
                db,
                actor_user_id=actor_user_id,
                action="session.revoked",
                resource_type="session",
                resource_id=session_token.id,
            )
            emit_event(
                db,
                event_type="session.revoked",
                resource_type="session",
                resource_id=session_token.id,
            )
        return session_token


class OrganizationModule:
    """Public Organization module service."""

    @staticmethod
    def require_membership_management(db: Session, *, organization_id: str, actor: User) -> str:
        actor_role = OrganizationModule.check_organization_role(
            db, organization_id=organization_id, user_id=actor.id
        )
        require(
            actor_role in {"Owner", "Maintainer"},
            "Organization membership cannot be managed.",
            status.HTTP_403_FORBIDDEN,
        )
        return type_cast(str, actor_role)

    @staticmethod
    def create_organization(db: Session, *, actor: User, name: str, slug: str) -> Organization:
        require(name.strip(), "Organization name is required.")
        require(slug.strip(), "Organization slug is required.")
        existing = db.scalar(select(Organization).where(Organization.slug == slug.strip().lower()))
        require(existing is None, "Organization slug already exists.", status.HTTP_409_CONFLICT)
        organization = Organization(name=name.strip(), slug=slug.strip().lower())
        db.add(organization)
        db.flush()
        db.add(
            OrganizationMembership(organization_id=organization.id, user_id=actor.id, role="Owner")
        )
        record_audit(
            db,
            actor_user_id=actor.id,
            action="organization.created",
            resource_type="organization",
            resource_id=organization.id,
            organization_id=organization.id,
        )
        emit_event(
            db,
            event_type="organization.created",
            resource_type="organization",
            resource_id=organization.id,
            organization_id=organization.id,
        )
        return organization

    @staticmethod
    def get_organization(db: Session, organization_id: str, actor: User) -> Organization:
        organization = db.get(Organization, organization_id)
        if organization is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found."
            )
        role = _membership_role(
            db,
            model=OrganizationMembership,
            field_name="organization_id",
            parent_id=organization.id,
            user_id=actor.id,
        )
        require(role is not None, "Organization access denied.", status.HTTP_403_FORBIDDEN)
        return organization

    @staticmethod
    def list_user_organizations(db: Session, actor: User) -> list[OrganizationMembership]:
        return list(
            db.scalars(
                select(OrganizationMembership)
                .options(joinedload(OrganizationMembership.organization))
                .where(OrganizationMembership.user_id == actor.id)
                .order_by(OrganizationMembership.created_at.desc())
            )
        )

    @staticmethod
    def add_member(
        db: Session, *, organization_id: str, user_id: str, role: str, actor: User
    ) -> OrganizationMembership:
        actor_role = OrganizationModule.require_membership_management(
            db, organization_id=organization_id, actor=actor
        )
        require(role in ORG_ROLE_PRIORITY, "Invalid Organization role.")
        target_user = get_user_or_404(db, user_id)
        OrganizationModule.get_organization(db, organization_id, actor)
        membership = db.scalar(
            select(OrganizationMembership).where(
                and_(
                    OrganizationMembership.organization_id == organization_id,
                    OrganizationMembership.user_id == user_id,
                )
            )
        )
        require(
            membership is None, "User is already an Organization member.", status.HTTP_409_CONFLICT
        )
        if role == "Owner":
            require(
                actor_role == "Owner",
                "Only an Owner can grant the Owner role.",
                status.HTTP_403_FORBIDDEN,
            )
        membership = OrganizationMembership(
            organization_id=organization_id, user_id=target_user.id, role=role
        )
        db.add(membership)
        db.flush()
        record_audit(
            db,
            actor_user_id=actor.id,
            action="organization.membership.created",
            resource_type="organization_membership",
            resource_id=membership.id,
            organization_id=organization_id,
            details={"target_user_id": target_user.id, "new_role": role},
        )
        emit_event(
            db,
            event_type="organization.membership.created",
            resource_type="organization_membership",
            resource_id=membership.id,
            organization_id=organization_id,
            payload={"target_user_id": target_user.id, "new_role": role},
        )
        return membership

    @staticmethod
    def resolve_registered_user(
        db: Session, *, user_id: str | None, user_email: str | None
    ) -> User:
        require(
            (user_id is None) != (user_email is None),
            "Provide exactly one of user_id or user_email.",
        )
        if user_id is not None:
            return get_user_or_404(db, user_id)
        normalized_email = (user_email or "").strip().lower()
        require(normalized_email, "User email is required.")
        user = db.scalar(select(User).where(User.email == normalized_email))
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Registered user not found."
            )
        return user

    @staticmethod
    def get_membership(
        db: Session, *, organization_id: str, membership_id: str
    ) -> OrganizationMembership:
        membership = db.scalar(
            select(OrganizationMembership)
            .options(joinedload(OrganizationMembership.user))
            .where(
                and_(
                    OrganizationMembership.id == membership_id,
                    OrganizationMembership.organization_id == organization_id,
                )
            )
        )
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Organization membership not found."
            )
        return membership

    @staticmethod
    def change_member_role(
        db: Session, *, organization_id: str, membership_id: str, role: str, actor: User
    ) -> OrganizationMembership:
        actor_role = OrganizationModule.require_membership_management(
            db, organization_id=organization_id, actor=actor
        )
        require(role in ORG_ROLE_PRIORITY, "Invalid Organization role.")
        membership = OrganizationModule.get_membership(
            db, organization_id=organization_id, membership_id=membership_id
        )
        previous_role = membership.role
        require(
            previous_role != role,
            "Organization member already has this role.",
            status.HTTP_409_CONFLICT,
        )
        if previous_role == "Owner" or role == "Owner":
            require(
                actor_role == "Owner",
                "Only an Owner can manage Owner roles.",
                status.HTTP_403_FORBIDDEN,
            )
        if previous_role == "Owner":
            owner_count = (
                db.scalar(
                    select(func.count())
                    .select_from(OrganizationMembership)
                    .where(
                        and_(
                            OrganizationMembership.organization_id == organization_id,
                            OrganizationMembership.role == "Owner",
                        )
                    )
                )
                or 0
            )
            require(
                owner_count > 1,
                "An Organization must retain at least one Owner.",
                status.HTTP_409_CONFLICT,
            )
        membership.role = role
        db.flush()
        details = {
            "target_user_id": membership.user_id,
            "previous_role": previous_role,
            "new_role": role,
        }
        record_audit(
            db,
            actor_user_id=actor.id,
            action="organization.membership.role_changed",
            resource_type="organization_membership",
            resource_id=membership.id,
            organization_id=organization_id,
            details=details,
        )
        emit_event(
            db,
            event_type="organization.membership.role_changed",
            resource_type="organization_membership",
            resource_id=membership.id,
            organization_id=organization_id,
            payload=details,
        )
        return membership

    @staticmethod
    def remove_member(
        db: Session, *, organization_id: str, membership_id: str, actor: User
    ) -> OrganizationMembership:
        actor_role = OrganizationModule.require_membership_management(
            db, organization_id=organization_id, actor=actor
        )
        membership = OrganizationModule.get_membership(
            db, organization_id=organization_id, membership_id=membership_id
        )
        if membership.role == "Owner":
            require(
                actor_role == "Owner",
                "Only an Owner can remove an Owner.",
                status.HTTP_403_FORBIDDEN,
            )
            owner_count = (
                db.scalar(
                    select(func.count())
                    .select_from(OrganizationMembership)
                    .where(
                        and_(
                            OrganizationMembership.organization_id == organization_id,
                            OrganizationMembership.role == "Owner",
                        )
                    )
                )
                or 0
            )
            require(
                owner_count > 1,
                "An Organization must retain at least one Owner.",
                status.HTTP_409_CONFLICT,
            )
        details = {"target_user_id": membership.user_id, "previous_role": membership.role}
        record_audit(
            db,
            actor_user_id=actor.id,
            action="organization.membership.removed",
            resource_type="organization_membership",
            resource_id=membership.id,
            organization_id=organization_id,
            details=details,
        )
        emit_event(
            db,
            event_type="organization.membership.removed",
            resource_type="organization_membership",
            resource_id=membership.id,
            organization_id=organization_id,
            payload=details,
        )
        db.delete(membership)
        db.flush()
        return membership

    @staticmethod
    def check_organization_role(db: Session, *, organization_id: str, user_id: str) -> str | None:
        return _membership_role(
            db,
            model=OrganizationMembership,
            field_name="organization_id",
            parent_id=organization_id,
            user_id=user_id,
        )

    @staticmethod
    def list_members(
        db: Session, *, organization_id: str, actor: User
    ) -> list[OrganizationMembership]:
        OrganizationModule.get_organization(db, organization_id, actor)
        return list(
            db.scalars(
                select(OrganizationMembership)
                .options(joinedload(OrganizationMembership.user))
                .where(OrganizationMembership.organization_id == organization_id)
            )
        )

    @staticmethod
    def list_members_page(
        db: Session,
        *,
        organization_id: str,
        actor: User,
        limit: int,
        cursor: str | None,
        role: str | None,
        query: str | None,
        sort: str,
        direction: str,
    ) -> PageResult[OrganizationMembership]:
        OrganizationModule.get_organization(db, organization_id, actor)
        validate_page_sort(sort, MEMBERSHIP_PAGE_SORTS)
        if role is not None:
            require(role in ORG_ROLE_PRIORITY, "Unsupported Organization role filter.")
        normalized_query = query.strip().lower() if query else ""
        statement = (
            select(OrganizationMembership)
            .options(joinedload(OrganizationMembership.user))
            .where(OrganizationMembership.organization_id == organization_id)
        )
        if role:
            statement = statement.where(OrganizationMembership.role == role)
        if normalized_query:
            statement = statement.join(User).where(
                or_(
                    func.lower(User.email).contains(normalized_query),
                    func.lower(User.display_name).contains(normalized_query),
                )
            )
        return paginate(
            db,
            statement=statement,
            model=OrganizationMembership,
            resource="organization-members",
            scope=repr((organization_id, role, normalized_query)),
            sort=sort,
            direction=direction,
            limit=limit,
            cursor=cursor,
        )


class ProjectModule:
    """Public Project module service."""

    @staticmethod
    def check_project_role(db: Session, *, project_id: str, user_id: str) -> str | None:
        return _membership_role(
            db,
            model=ProjectMembership,
            field_name="project_id",
            parent_id=project_id,
            user_id=user_id,
        )

    @staticmethod
    def require_project_permission(
        db: Session,
        *,
        project_id: str,
        actor: User,
        permission: str,
    ) -> Project:
        project = db.get(Project, project_id)
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
        org_role = _membership_role(
            db,
            model=OrganizationMembership,
            field_name="organization_id",
            parent_id=project.organization_id,
            user_id=actor.id,
        )
        require(org_role is not None, "Project access denied.", status.HTTP_403_FORBIDDEN)
        project_role = ProjectModule.check_project_role(db, project_id=project_id, user_id=actor.id)
        require(
            project_role in PROJECT_PERMISSION_ROLES[permission],
            "Project permission denied.",
            status.HTTP_403_FORBIDDEN,
        )
        return project

    @staticmethod
    def create_project(
        db: Session,
        *,
        organization_id: str,
        name: str,
        description: str,
        actor: User,
    ) -> Project:
        actor_org_role = _membership_role(
            db,
            model=OrganizationMembership,
            field_name="organization_id",
            parent_id=organization_id,
            user_id=actor.id,
        )
        require(
            actor_org_role in {"Owner", "Maintainer"},
            "Project cannot be created.",
            status.HTTP_403_FORBIDDEN,
        )
        organization = db.get(Organization, organization_id)
        if organization is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found."
            )
        project = Project(
            organization_id=organization_id, name=name.strip(), description=description.strip()
        )
        db.add(project)
        db.flush()
        db.add(ProjectMembership(project_id=project.id, user_id=actor.id, role="Owner"))
        record_audit(
            db,
            actor_user_id=actor.id,
            action="project.created",
            resource_type="project",
            resource_id=project.id,
            organization_id=organization_id,
            project_id=project.id,
        )
        emit_event(
            db,
            event_type="project.created",
            resource_type="project",
            resource_id=project.id,
            organization_id=organization_id,
            project_id=project.id,
        )
        return project

    @staticmethod
    def get_project(db: Session, *, project_id: str, actor: User) -> Project:
        return ProjectModule.require_project_permission(
            db, project_id=project_id, actor=actor, permission="read_project"
        )

    @staticmethod
    def list_organization_projects(
        db: Session, *, organization_id: str, actor: User
    ) -> list[Project]:
        OrganizationModule.get_organization(db, organization_id, actor)
        statement = (
            select(Project)
            .where(Project.organization_id == organization_id)
            .order_by(Project.created_at.desc())
        )
        return list(db.scalars(statement))

    @staticmethod
    def list_user_projects(
        db: Session, *, organization_id: str, actor: User
    ) -> list[ProjectMembership]:
        OrganizationModule.get_organization(db, organization_id, actor)
        return list(
            db.scalars(
                select(ProjectMembership)
                .options(joinedload(ProjectMembership.project))
                .join(Project, Project.id == ProjectMembership.project_id)
                .where(
                    and_(
                        Project.organization_id == organization_id,
                        ProjectMembership.user_id == actor.id,
                    )
                )
            )
        )

    @staticmethod
    def add_member(
        db: Session, *, project_id: str, user_id: str, role: str, actor: User
    ) -> ProjectMembership:
        project = ProjectModule.require_project_permission(
            db, project_id=project_id, actor=actor, permission="manage_members"
        )
        require(role in PROJECT_ROLE_PRIORITY, "Invalid Project role.")
        org_role = OrganizationModule.check_organization_role(
            db, organization_id=project.organization_id, user_id=user_id
        )
        require(
            org_role is not None, "User must belong to the Organization before joining the Project."
        )
        get_user_or_404(db, user_id)
        membership = db.scalar(
            select(ProjectMembership).where(
                and_(
                    ProjectMembership.project_id == project_id, ProjectMembership.user_id == user_id
                )
            )
        )
        require(membership is None, "User is already a Project member.", status.HTTP_409_CONFLICT)
        actor_role = ProjectModule.check_project_role(db, project_id=project_id, user_id=actor.id)
        if role == "Owner":
            require(
                actor_role == "Owner",
                "Only an Owner can grant the Owner role.",
                status.HTTP_403_FORBIDDEN,
            )
        membership = ProjectMembership(project_id=project_id, user_id=user_id, role=role)
        db.add(membership)
        db.flush()
        record_audit(
            db,
            actor_user_id=actor.id,
            action="project.membership.created",
            resource_type="project_membership",
            resource_id=membership.id,
            organization_id=project.organization_id,
            project_id=project.id,
            details={"target_user_id": user_id, "new_role": role},
        )
        emit_event(
            db,
            event_type="project.membership.created",
            resource_type="project_membership",
            resource_id=membership.id,
            organization_id=project.organization_id,
            project_id=project.id,
            payload={"target_user_id": user_id, "new_role": role},
        )
        return membership

    @staticmethod
    def get_membership(db: Session, *, project_id: str, membership_id: str) -> ProjectMembership:
        membership = db.scalar(
            select(ProjectMembership)
            .options(joinedload(ProjectMembership.user))
            .where(
                and_(
                    ProjectMembership.id == membership_id,
                    ProjectMembership.project_id == project_id,
                )
            )
        )
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project membership not found."
            )
        return membership

    @staticmethod
    def change_member_role(
        db: Session, *, project_id: str, membership_id: str, role: str, actor: User
    ) -> ProjectMembership:
        project = ProjectModule.require_project_permission(
            db, project_id=project_id, actor=actor, permission="manage_members"
        )
        require(role in PROJECT_ROLE_PRIORITY, "Invalid Project role.")
        actor_role = ProjectModule.check_project_role(db, project_id=project_id, user_id=actor.id)
        membership = ProjectModule.get_membership(
            db, project_id=project_id, membership_id=membership_id
        )
        previous_role = membership.role
        require(
            previous_role != role, "Project member already has this role.", status.HTTP_409_CONFLICT
        )
        if previous_role == "Owner" or role == "Owner":
            require(
                actor_role == "Owner",
                "Only an Owner can manage Owner roles.",
                status.HTTP_403_FORBIDDEN,
            )
        if previous_role == "Owner":
            owner_count = (
                db.scalar(
                    select(func.count())
                    .select_from(ProjectMembership)
                    .where(
                        and_(
                            ProjectMembership.project_id == project_id,
                            ProjectMembership.role == "Owner",
                        )
                    )
                )
                or 0
            )
            require(
                owner_count > 1,
                "A Project must retain at least one Owner.",
                status.HTTP_409_CONFLICT,
            )
        membership.role = role
        db.flush()
        details = {
            "target_user_id": membership.user_id,
            "previous_role": previous_role,
            "new_role": role,
        }
        record_audit(
            db,
            actor_user_id=actor.id,
            action="project.membership.role_changed",
            resource_type="project_membership",
            resource_id=membership.id,
            organization_id=project.organization_id,
            project_id=project.id,
            details=details,
        )
        emit_event(
            db,
            event_type="project.membership.role_changed",
            resource_type="project_membership",
            resource_id=membership.id,
            organization_id=project.organization_id,
            project_id=project.id,
            payload=details,
        )
        return membership

    @staticmethod
    def remove_member(
        db: Session, *, project_id: str, membership_id: str, actor: User
    ) -> ProjectMembership:
        project = ProjectModule.require_project_permission(
            db, project_id=project_id, actor=actor, permission="manage_members"
        )
        actor_role = ProjectModule.check_project_role(db, project_id=project_id, user_id=actor.id)
        membership = ProjectModule.get_membership(
            db, project_id=project_id, membership_id=membership_id
        )
        if membership.role == "Owner":
            require(
                actor_role == "Owner",
                "Only an Owner can remove an Owner.",
                status.HTTP_403_FORBIDDEN,
            )
            owner_count = (
                db.scalar(
                    select(func.count())
                    .select_from(ProjectMembership)
                    .where(
                        and_(
                            ProjectMembership.project_id == project_id,
                            ProjectMembership.role == "Owner",
                        )
                    )
                )
                or 0
            )
            require(
                owner_count > 1,
                "A Project must retain at least one Owner.",
                status.HTTP_409_CONFLICT,
            )
        details = {"target_user_id": membership.user_id, "previous_role": membership.role}
        record_audit(
            db,
            actor_user_id=actor.id,
            action="project.membership.removed",
            resource_type="project_membership",
            resource_id=membership.id,
            organization_id=project.organization_id,
            project_id=project.id,
            details=details,
        )
        emit_event(
            db,
            event_type="project.membership.removed",
            resource_type="project_membership",
            resource_id=membership.id,
            organization_id=project.organization_id,
            project_id=project.id,
            payload=details,
        )
        db.delete(membership)
        db.flush()
        return membership

    @staticmethod
    def remove_user_memberships_for_organization(
        db: Session, *, organization_id: str, user_id: str, actor: User
    ) -> list[ProjectMembership]:
        memberships = list(
            db.scalars(
                select(ProjectMembership)
                .options(joinedload(ProjectMembership.project))
                .join(Project, Project.id == ProjectMembership.project_id)
                .where(
                    and_(
                        Project.organization_id == organization_id,
                        ProjectMembership.user_id == user_id,
                    )
                )
            )
        )
        for membership in memberships:
            if membership.role == "Owner":
                owner_count = (
                    db.scalar(
                        select(func.count())
                        .select_from(ProjectMembership)
                        .where(
                            and_(
                                ProjectMembership.project_id == membership.project_id,
                                ProjectMembership.role == "Owner",
                            )
                        )
                    )
                    or 0
                )
                require(
                    owner_count > 1,
                    "Organization member owns a Project that must retain at least one Owner.",
                    status.HTTP_409_CONFLICT,
                )
        for membership in memberships:
            details = {"target_user_id": user_id, "previous_role": membership.role}
            record_audit(
                db,
                actor_user_id=actor.id,
                action="project.membership.removed",
                resource_type="project_membership",
                resource_id=membership.id,
                organization_id=organization_id,
                project_id=membership.project_id,
                details=details,
            )
            emit_event(
                db,
                event_type="project.membership.removed",
                resource_type="project_membership",
                resource_id=membership.id,
                organization_id=organization_id,
                project_id=membership.project_id,
                payload=details,
            )
            db.delete(membership)
        db.flush()
        return memberships

    @staticmethod
    def list_members(db: Session, *, project_id: str, actor: User) -> list[ProjectMembership]:
        ProjectModule.require_project_permission(
            db, project_id=project_id, actor=actor, permission="read_project"
        )
        return list(
            db.scalars(
                select(ProjectMembership)
                .options(joinedload(ProjectMembership.user))
                .where(ProjectMembership.project_id == project_id)
            )
        )

    @staticmethod
    def list_readable_members(db: Session, *, project_id: str) -> list[ProjectMembership]:
        """Return current Project members who still have read access."""
        return list(
            db.scalars(
                select(ProjectMembership)
                .options(joinedload(ProjectMembership.user))
                .join(Project, Project.id == ProjectMembership.project_id)
                .join(
                    OrganizationMembership,
                    and_(
                        OrganizationMembership.organization_id == Project.organization_id,
                        OrganizationMembership.user_id == ProjectMembership.user_id,
                    ),
                )
                .where(
                    and_(
                        ProjectMembership.project_id == project_id,
                        ProjectMembership.role.in_(PROJECT_PERMISSION_ROLES["read_project"]),
                    )
                )
            )
        )

    @staticmethod
    def list_members_page(
        db: Session,
        *,
        project_id: str,
        actor: User,
        limit: int,
        cursor: str | None,
        role: str | None,
        query: str | None,
        sort: str,
        direction: str,
    ) -> PageResult[ProjectMembership]:
        ProjectModule.require_project_permission(
            db, project_id=project_id, actor=actor, permission="read_project"
        )
        validate_page_sort(sort, MEMBERSHIP_PAGE_SORTS)
        if role is not None:
            require(role in PROJECT_ROLE_PRIORITY, "Unsupported Project role filter.")
        normalized_query = query.strip().lower() if query else ""
        statement = (
            select(ProjectMembership)
            .options(joinedload(ProjectMembership.user))
            .where(ProjectMembership.project_id == project_id)
        )
        if role:
            statement = statement.where(ProjectMembership.role == role)
        if normalized_query:
            statement = statement.join(User).where(
                or_(
                    func.lower(User.email).contains(normalized_query),
                    func.lower(User.display_name).contains(normalized_query),
                )
            )
        return paginate(
            db,
            statement=statement,
            model=ProjectMembership,
            resource="project-members",
            scope=repr((project_id, role, normalized_query)),
            sort=sort,
            direction=direction,
            limit=limit,
            cursor=cursor,
        )

    @staticmethod
    def create_asset_view(
        db: Session,
        *,
        actor: User,
        project_id: str,
        name: str,
        filters: dict[str, object],
        sort: dict[str, object],
        density: str,
        selected_columns: list[str],
    ) -> ProjectAssetView:
        project = ProjectModule.require_project_permission(
            db, project_id=project_id, actor=actor, permission="read_project"
        )
        normalized_name = name.strip()
        require(bool(normalized_name), "Saved view name is required.")
        require(density in {"compact", "comfortable"}, "Unsupported saved view density.")
        existing = db.scalar(
            select(ProjectAssetView).where(
                and_(
                    ProjectAssetView.owner_user_id == actor.id,
                    ProjectAssetView.project_id == project_id,
                    ProjectAssetView.name == normalized_name,
                )
            )
        )
        require(
            existing is None,
            "A saved view with this name already exists.",
            status.HTTP_409_CONFLICT,
        )
        view = ProjectAssetView(
            owner_user_id=actor.id,
            project_id=project_id,
            name=normalized_name,
            filters=filters,
            sort=sort,
            density=density,
            selected_columns=selected_columns,
        )
        db.add(view)
        db.flush()
        record_audit(
            db,
            actor_user_id=actor.id,
            action="project_asset_view.created",
            resource_type="project_asset_view",
            resource_id=view.id,
            organization_id=project.organization_id,
            project_id=project.id,
        )
        return view

    @staticmethod
    def list_asset_views(
        db: Session, *, actor: User, project_id: str | None = None
    ) -> list[ProjectAssetView]:
        statement = (
            select(ProjectAssetView)
            .join(Project, Project.id == ProjectAssetView.project_id)
            .join(
                ProjectMembership,
                and_(
                    ProjectMembership.project_id == Project.id,
                    ProjectMembership.user_id == actor.id,
                    ProjectMembership.role.in_(PROJECT_PERMISSION_ROLES["read_project"]),
                ),
            )
            .join(
                OrganizationMembership,
                and_(
                    OrganizationMembership.organization_id == Project.organization_id,
                    OrganizationMembership.user_id == actor.id,
                ),
            )
            .where(ProjectAssetView.owner_user_id == actor.id)
        )
        if project_id is not None:
            ProjectModule.require_project_permission(
                db, project_id=project_id, actor=actor, permission="read_project"
            )
            statement = statement.where(ProjectAssetView.project_id == project_id)
        return list(db.scalars(statement.order_by(ProjectAssetView.name, ProjectAssetView.id)))

    @staticmethod
    def get_asset_view(db: Session, *, actor: User, view_id: str) -> ProjectAssetView:
        view = db.scalar(
            select(ProjectAssetView).where(
                and_(ProjectAssetView.id == view_id, ProjectAssetView.owner_user_id == actor.id)
            )
        )
        if view is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Saved view not found."
            )
        ProjectModule.require_project_permission(
            db, project_id=view.project_id, actor=actor, permission="read_project"
        )
        return view

    @staticmethod
    def update_asset_view(
        db: Session,
        *,
        actor: User,
        view_id: str,
        name: str,
        filters: dict[str, object],
        sort: dict[str, object],
        density: str,
        selected_columns: list[str],
    ) -> ProjectAssetView:
        view = ProjectModule.get_asset_view(db, actor=actor, view_id=view_id)
        normalized_name = name.strip()
        require(bool(normalized_name), "Saved view name is required.")
        require(density in {"compact", "comfortable"}, "Unsupported saved view density.")
        duplicate = db.scalar(
            select(ProjectAssetView).where(
                and_(
                    ProjectAssetView.owner_user_id == actor.id,
                    ProjectAssetView.project_id == view.project_id,
                    ProjectAssetView.name == normalized_name,
                    ProjectAssetView.id != view.id,
                )
            )
        )
        require(
            duplicate is None,
            "A saved view with this name already exists.",
            status.HTTP_409_CONFLICT,
        )
        view.name = normalized_name
        view.filters = filters
        view.sort = sort
        view.density = density
        view.selected_columns = selected_columns
        view.updated_at = utc_now()
        project = db.get(Project, view.project_id)
        record_audit(
            db,
            actor_user_id=actor.id,
            action="project_asset_view.updated",
            resource_type="project_asset_view",
            resource_id=view.id,
            organization_id=project.organization_id if project else None,
            project_id=view.project_id,
        )
        return view

    @staticmethod
    def delete_asset_view(db: Session, *, actor: User, view_id: str) -> ProjectAssetView:
        view = ProjectModule.get_asset_view(db, actor=actor, view_id=view_id)
        project = db.get(Project, view.project_id)
        record_audit(
            db,
            actor_user_id=actor.id,
            action="project_asset_view.deleted",
            resource_type="project_asset_view",
            resource_id=view.id,
            organization_id=project.organization_id if project else None,
            project_id=view.project_id,
        )
        db.delete(view)
        db.flush()
        return view


class NotificationsModule:
    """Public in-app notifications service for Phase 2 collaboration."""

    @staticmethod
    def _visible_project_ids_for_user(db: Session, *, user_id: str) -> set[str]:
        rows = db.execute(
            select(ProjectMembership.project_id)
            .join(Project, Project.id == ProjectMembership.project_id)
            .join(
                OrganizationMembership,
                and_(
                    OrganizationMembership.organization_id == Project.organization_id,
                    OrganizationMembership.user_id == ProjectMembership.user_id,
                ),
            )
            .where(
                and_(
                    ProjectMembership.user_id == user_id,
                    ProjectMembership.role.in_(PROJECT_PERMISSION_ROLES["read_project"]),
                )
            )
        )
        return {str(project_id) for project_id in rows.scalars()}

    @staticmethod
    def create_notifications(
        db: Session,
        *,
        organization_id: str | None,
        project_id: str,
        asset_id: str | None,
        revision_id: str | None,
        event_type: str,
        actor_user_id: str | None,
        recipient_user_ids: list[str],
        details: dict[str, object] | None = None,
    ) -> list[NotificationRecord]:
        created: list[NotificationRecord] = []
        payload = dict(details or {})
        for recipient_user_id in recipient_user_ids:
            notification = NotificationRecord(
                recipient_user_id=recipient_user_id,
                actor_user_id=actor_user_id,
                organization_id=organization_id,
                project_id=project_id,
                asset_id=asset_id,
                revision_id=revision_id,
                event_type=event_type,
                details=payload,
            )
            db.add(notification)
            db.flush()
            created.append(notification)
            record_audit(
                db,
                actor_user_id=actor_user_id,
                action="notification.emitted",
                resource_type="notification",
                resource_id=notification.id,
                organization_id=organization_id,
                project_id=project_id,
                details={
                    "recipient_user_id": recipient_user_id,
                    "notification_event_type": event_type,
                    **payload,
                },
            )
            emit_event(
                db,
                event_type="notification.emitted",
                resource_type="notification",
                resource_id=notification.id,
                organization_id=organization_id,
                project_id=project_id,
                payload={
                    "recipient_user_id": recipient_user_id,
                    "notification_event_type": event_type,
                    **payload,
                },
            )
        return created

    @staticmethod
    def notify_project_members(
        db: Session,
        *,
        organization_id: str | None,
        project_id: str,
        asset_id: str | None,
        revision_id: str | None,
        event_type: str,
        actor_user_id: str | None,
        details: dict[str, object] | None = None,
        include_actor: bool = False,
        recipient_user_ids: list[str] | None = None,
    ) -> list[NotificationRecord]:
        if recipient_user_ids is None:
            members = ProjectModule.list_readable_members(db, project_id=project_id)
            recipient_user_ids = [item.user_id for item in members]
        unique_recipient_user_ids: list[str] = []
        seen: set[str] = set()
        for recipient_user_id in recipient_user_ids:
            if recipient_user_id in seen:
                continue
            seen.add(recipient_user_id)
            if (
                actor_user_id is not None
                and not include_actor
                and recipient_user_id == actor_user_id
            ):
                continue
            unique_recipient_user_ids.append(recipient_user_id)
        if not unique_recipient_user_ids:
            return []
        return NotificationsModule.create_notifications(
            db,
            organization_id=organization_id,
            project_id=project_id,
            asset_id=asset_id,
            revision_id=revision_id,
            event_type=event_type,
            actor_user_id=actor_user_id,
            recipient_user_ids=unique_recipient_user_ids,
            details=details,
        )

    @staticmethod
    def list_notifications(db: Session, *, actor: User) -> list[NotificationRecord]:
        visible_project_ids = NotificationsModule._visible_project_ids_for_user(
            db, user_id=actor.id
        )
        if not visible_project_ids:
            return []
        return list(
            db.scalars(
                select(NotificationRecord)
                .where(
                    and_(
                        NotificationRecord.recipient_user_id == actor.id,
                        NotificationRecord.project_id.in_(visible_project_ids),
                    )
                )
                .order_by(NotificationRecord.created_at.desc())
            )
        )

    @staticmethod
    def list_notifications_page(
        db: Session,
        *,
        actor: User,
        limit: int,
        cursor: str | None,
        project_id: str | None,
        is_read: bool | None,
        sort: str,
        direction: str,
    ) -> PageResult[NotificationRecord]:
        validate_page_sort(sort, NOTIFICATION_PAGE_SORTS)
        visible_project_ids = NotificationsModule._visible_project_ids_for_user(
            db, user_id=actor.id
        )
        if project_id is not None:
            require(
                project_id in visible_project_ids,
                "Notification Project access denied.",
                status.HTTP_403_FORBIDDEN,
            )
        statement = select(NotificationRecord).where(
            and_(
                NotificationRecord.recipient_user_id == actor.id,
                NotificationRecord.project_id.in_(visible_project_ids),
            )
        )
        if project_id is not None:
            statement = statement.where(NotificationRecord.project_id == project_id)
        if is_read is not None:
            statement = statement.where(NotificationRecord.is_read == is_read)
        return paginate(
            db,
            statement=statement,
            model=NotificationRecord,
            resource="notifications",
            scope=repr((actor.id, project_id, is_read)),
            sort=sort,
            direction=direction,
            limit=limit,
            cursor=cursor,
        )

    @staticmethod
    def mark_read_many(
        db: Session,
        *,
        actor: User,
        notification_ids: list[str],
        all_matching: bool,
        project_id: str | None,
        is_read: bool | None,
    ) -> list[NotificationRecord]:
        visible_project_ids = NotificationsModule._visible_project_ids_for_user(
            db, user_id=actor.id
        )
        if project_id is not None:
            require(
                project_id in visible_project_ids,
                "Notification Project access denied.",
                status.HTTP_403_FORBIDDEN,
            )
        unique_ids = list(dict.fromkeys(notification_ids))
        statement = select(NotificationRecord).where(
            and_(
                NotificationRecord.recipient_user_id == actor.id,
                NotificationRecord.project_id.in_(visible_project_ids),
            )
        )
        if all_matching:
            if project_id is not None:
                statement = statement.where(NotificationRecord.project_id == project_id)
            if is_read is not None:
                statement = statement.where(NotificationRecord.is_read == is_read)
        else:
            statement = statement.where(NotificationRecord.id.in_(unique_ids))
        notifications = list(db.scalars(statement))
        if not all_matching and len(notifications) != len(unique_ids):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or more notifications were not found.",
            )
        changed: list[NotificationRecord] = []
        read_at = utc_now()
        for notification in notifications:
            if notification.is_read:
                continue
            notification.is_read = True
            notification.read_at = read_at
            changed.append(notification)
            record_audit(
                db,
                actor_user_id=actor.id,
                action="notification.read",
                resource_type="notification",
                resource_id=notification.id,
                organization_id=notification.organization_id,
                project_id=notification.project_id,
                details={"notification_event_type": notification.event_type},
            )
            emit_event(
                db,
                event_type="notification.read",
                resource_type="notification",
                resource_id=notification.id,
                organization_id=notification.organization_id,
                project_id=notification.project_id,
                payload={"notification_event_type": notification.event_type},
            )
        return changed

    @staticmethod
    def mark_read(db: Session, *, notification_id: str, actor: User) -> NotificationRecord:
        notification = db.get(NotificationRecord, notification_id)
        if notification is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found.",
            )
        require(
            notification.recipient_user_id == actor.id,
            "Notification access denied.",
            status.HTTP_403_FORBIDDEN,
        )
        visible_project_ids = NotificationsModule._visible_project_ids_for_user(
            db, user_id=actor.id
        )
        require(
            notification.project_id in visible_project_ids,
            "Notification access denied.",
            status.HTTP_403_FORBIDDEN,
        )
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = utc_now()
            record_audit(
                db,
                actor_user_id=actor.id,
                action="notification.read",
                resource_type="notification",
                resource_id=notification.id,
                organization_id=notification.organization_id,
                project_id=notification.project_id,
                details={"notification_event_type": notification.event_type},
            )
            emit_event(
                db,
                event_type="notification.read",
                resource_type="notification",
                resource_id=notification.id,
                organization_id=notification.organization_id,
                project_id=notification.project_id,
                payload={"notification_event_type": notification.event_type},
            )
        return notification


class BlobModule:
    """Public Blobs module service."""

    @staticmethod
    async def upload_blob(
        db: Session,
        *,
        actor: User,
        file: UploadFile,
        storage: BlobStorage,
    ) -> Blob:
        content = await file.read()
        checksum = hashlib.sha256(content).hexdigest()
        raw_filename = file.filename or "blob.bin"
        safe_filename = PurePath(raw_filename).name or "blob.bin"
        storage_key = f"{utc_now().strftime('%Y/%m/%d')}/{secrets.token_hex(16)}-{safe_filename}"
        storage.put_bytes(storage_key, content, file.content_type)
        blob = Blob(
            storage_key=storage_key,
            filename=safe_filename,
            media_type=file.content_type or "application/octet-stream",
            size_bytes=len(content),
            checksum_sha256=checksum,
            created_by_user_id=actor.id,
        )
        db.add(blob)
        db.flush()
        record_audit(
            db,
            actor_user_id=actor.id,
            action="blob.uploaded",
            resource_type="blob",
            resource_id=blob.id,
        )
        emit_event(db, event_type="blob.uploaded", resource_type="blob", resource_id=blob.id)
        return blob

    @staticmethod
    def download_blob(
        db: Session,
        *,
        blob_id: str,
        actor: User,
        storage: BlobStorage,
    ) -> tuple[Blob, bytes]:
        blob = db.scalar(
            select(Blob)
            .options(
                joinedload(Blob.created_by),
                joinedload(Blob.representations)
                .joinedload(Representation.revision)
                .joinedload(Revision.asset)
                .joinedload(Asset.project),
            )
            .where(Blob.id == blob_id)
        )
        if blob is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blob not found.")
        if blob.representations:
            readable_project_ids = {
                representation.revision.asset.project_id
                for representation in blob.representations
                if representation.revision is not None and representation.revision.asset is not None
            }
            require(readable_project_ids, "Blob is not linked to a readable Asset.")
            for project_id in readable_project_ids:
                try:
                    ProjectModule.require_project_permission(
                        db,
                        project_id=project_id,
                        actor=actor,
                        permission="read_project",
                    )
                    break
                except HTTPException:
                    continue
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Blob access denied.",
                )
        else:
            require(
                blob.created_by_user_id == actor.id,
                "Blob access denied.",
                status.HTTP_403_FORBIDDEN,
            )
        return blob, storage.get_bytes(blob.storage_key)


class AssetsModule:
    """Public Assets module service."""

    @staticmethod
    def create_asset(
        db: Session, *, project_id: str, name: str, description: str, actor: User
    ) -> Asset:
        project = ProjectModule.require_project_permission(
            db,
            project_id=project_id,
            actor=actor,
            permission="create_asset",
        )
        asset = Asset(
            project_id=project.id,
            name=name.strip(),
            description=description.strip(),
            created_by_user_id=actor.id,
        )
        db.add(asset)
        db.flush()
        record_audit(
            db,
            actor_user_id=actor.id,
            action="asset.created",
            resource_type="asset",
            resource_id=asset.id,
            organization_id=project.organization_id,
            project_id=project.id,
        )
        emit_event(
            db,
            event_type="asset.created",
            resource_type="asset",
            resource_id=asset.id,
            organization_id=project.organization_id,
            project_id=project.id,
        )
        return asset

    @staticmethod
    def list_assets(db: Session, *, project_id: str, actor: User) -> list[Asset]:
        ProjectModule.require_project_permission(
            db,
            project_id=project_id,
            actor=actor,
            permission="read_project",
        )
        statement = (
            select(Asset).where(Asset.project_id == project_id).order_by(Asset.created_at.desc())
        )
        return list(db.scalars(statement))

    @staticmethod
    def validate_asset_view_definition(
        *,
        filters: dict[str, object],
        sort: dict[str, object],
        selected_columns: list[str],
    ) -> None:
        unknown_filters = set(filters) - {"query", "status"}
        require(not unknown_filters, "Unsupported Asset saved-view filter.")
        status_filter = filters.get("status")
        if status_filter is not None:
            require(
                isinstance(status_filter, str) and status_filter in ALLOWED_STATUSES,
                "Unsupported Asset status filter.",
            )
        query = filters.get("query")
        require(query is None or isinstance(query, str), "Asset query filter must be text.")
        require(set(sort) == {"field", "direction"}, "Asset saved-view sort is incomplete.")
        field = sort.get("field")
        direction = sort.get("direction")
        require(
            isinstance(field, str) and field in ASSET_PAGE_SORTS,
            "Unsupported Asset sort key.",
        )
        require(direction in {"asc", "desc"}, "Unsupported Asset sort direction.")
        require(
            bool(selected_columns) and set(selected_columns) <= ASSET_VIEW_COLUMNS,
            "Unsupported Asset saved-view column.",
        )
        require(
            len(selected_columns) == len(set(selected_columns)),
            "Asset saved-view columns must be unique.",
        )

    @staticmethod
    def list_assets_page(
        db: Session,
        *,
        project_id: str,
        actor: User,
        limit: int,
        cursor: str | None,
        status_filter: str | None,
        query: str | None,
        sort: str,
        direction: str,
    ) -> PageResult[Asset]:
        ProjectModule.require_project_permission(
            db, project_id=project_id, actor=actor, permission="read_project"
        )
        validate_page_sort(sort, ASSET_PAGE_SORTS)
        if status_filter is not None:
            require(status_filter in ALLOWED_STATUSES, "Unsupported Asset status filter.")
        normalized_query = query.strip().lower() if query else ""
        statement = select(Asset).where(Asset.project_id == project_id)
        if status_filter:
            statement = statement.where(Asset.status == status_filter)
        if normalized_query:
            statement = statement.where(
                or_(
                    func.lower(Asset.name).contains(normalized_query),
                    func.lower(Asset.description).contains(normalized_query),
                )
            )
        return paginate(
            db,
            statement=statement,
            model=Asset,
            resource="project-assets",
            scope=repr((project_id, status_filter, normalized_query)),
            sort=sort,
            direction=direction,
            limit=limit,
            cursor=cursor,
        )

    @staticmethod
    def get_asset(db: Session, *, asset_id: str, actor: User) -> Asset:
        asset = db.scalar(
            select(Asset)
            .options(
                joinedload(Asset.revisions)
                .joinedload(Revision.representations)
                .joinedload(Representation.blob),
                joinedload(Asset.project),
            )
            .where(Asset.id == asset_id)
        )
        if asset is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
        ProjectModule.require_project_permission(
            db,
            project_id=asset.project_id,
            actor=actor,
            permission="read_project",
        )
        return asset

    @staticmethod
    def update_status(db: Session, *, asset_id: str, status_value: str, actor: User) -> Asset:
        asset = AssetsModule.get_asset(db, asset_id=asset_id, actor=actor)
        ProjectModule.require_project_permission(
            db,
            project_id=asset.project_id,
            actor=actor,
            permission="update_asset",
        )
        require(status_value in ALLOWED_STATUSES, "Invalid lifecycle status.")
        asset.status = status_value
        asset.updated_at = utc_now()
        record_audit(
            db,
            actor_user_id=actor.id,
            action="asset.status.updated",
            resource_type="asset",
            resource_id=asset.id,
            organization_id=asset.project.organization_id,
            project_id=asset.project_id,
            details={"status": status_value},
        )
        emit_event(
            db,
            event_type="asset.status.updated",
            resource_type="asset",
            resource_id=asset.id,
            organization_id=asset.project.organization_id,
            project_id=asset.project_id,
            payload={"status": status_value},
        )
        return asset

    @staticmethod
    def create_revision(db: Session, *, asset_id: str, comment: str, actor: User) -> Revision:
        asset = AssetsModule.get_asset(db, asset_id=asset_id, actor=actor)
        ProjectModule.require_project_permission(
            db,
            project_id=asset.project_id,
            actor=actor,
            permission="create_revision",
        )
        next_number = (
            db.scalar(
                select(func.coalesce(func.max(Revision.number), 0) + 1).where(
                    Revision.asset_id == asset.id
                )
            )
            or 1
        )
        revision = Revision(
            asset_id=asset.id,
            number=next_number,
            comment=comment.strip(),
            created_by_user_id=actor.id,
        )
        db.add(revision)
        asset.updated_at = utc_now()
        db.flush()
        record_audit(
            db,
            actor_user_id=actor.id,
            action="revision.created",
            resource_type="revision",
            resource_id=revision.id,
            organization_id=asset.project.organization_id,
            project_id=asset.project_id,
            details={"asset_id": asset.id, "number": next_number},
        )
        emit_event(
            db,
            event_type="revision.created",
            resource_type="revision",
            resource_id=revision.id,
            organization_id=asset.project.organization_id,
            project_id=asset.project_id,
            payload={"asset_id": asset.id, "number": next_number},
        )
        NotificationsModule.notify_project_members(
            db,
            organization_id=asset.project.organization_id,
            project_id=asset.project_id,
            asset_id=asset.id,
            revision_id=revision.id,
            event_type="revision.created",
            actor_user_id=actor.id,
            details={"asset_id": asset.id, "revision_number": next_number},
        )
        return revision

    @staticmethod
    def add_representation(
        db: Session,
        *,
        revision_id: str,
        name: str,
        media_type: str,
        blob_id: str | None,
        actor: User,
    ) -> Representation:
        revision = db.scalar(
            select(Revision)
            .options(joinedload(Revision.asset).joinedload(Asset.project))
            .where(Revision.id == revision_id)
        )
        if revision is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revision not found.")
        ProjectModule.require_project_permission(
            db, project_id=revision.asset.project_id, actor=actor, permission="create_revision"
        )
        if blob_id is not None:
            blob = db.get(Blob, blob_id)
            if blob is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blob not found.")
        representation = Representation(
            revision_id=revision.id,
            name=name.strip(),
            media_type=media_type.strip(),
            blob_id=blob_id,
        )
        db.add(representation)
        db.flush()
        record_audit(
            db,
            actor_user_id=actor.id,
            action="representation.created",
            resource_type="representation",
            resource_id=representation.id,
            organization_id=revision.asset.project.organization_id,
            project_id=revision.asset.project_id,
        )
        emit_event(
            db,
            event_type="representation.created",
            resource_type="representation",
            resource_id=representation.id,
            organization_id=revision.asset.project.organization_id,
            project_id=revision.asset.project_id,
        )
        return representation

    @staticmethod
    def list_history(db: Session, *, asset_id: str, actor: User) -> list[Revision]:
        asset = AssetsModule.get_asset(db, asset_id=asset_id, actor=actor)
        statement = (
            select(Revision)
            .options(joinedload(Revision.representations).joinedload(Representation.blob))
            .where(Revision.asset_id == asset.id)
            .order_by(Revision.number.desc())
        )
        return list(db.execute(statement).unique().scalars())


class RelationshipsModule:
    """Public relationships module service for Phase 3."""

    @staticmethod
    def _normalize_metadata(metadata: dict[str, object] | None) -> dict[str, object]:
        require(
            metadata is None or isinstance(metadata, dict),
            "Relationship metadata must be an object.",
        )
        return dict(metadata or {})

    @staticmethod
    def _require_relationship_type(relationship_type: str) -> str:
        normalized = relationship_type.strip()
        require(normalized in ALLOWED_RELATIONSHIP_TYPES, "Invalid relationship type.")
        return normalized

    @staticmethod
    def _require_reference_type(reference_type: str) -> str:
        normalized = reference_type.strip()
        require(normalized, "Reference type is required.")
        return normalized

    @staticmethod
    def _get_asset(
        db: Session,
        *,
        asset_id: str,
        actor: User,
        permission: str = "read_project",
    ) -> Asset:
        asset = AssetsModule.get_asset(db, asset_id=asset_id, actor=actor)
        ProjectModule.require_project_permission(
            db,
            project_id=asset.project_id,
            actor=actor,
            permission=permission,
        )
        return asset

    @staticmethod
    def _require_same_project(source_asset: Asset, target_asset: Asset) -> None:
        require(
            source_asset.project_id == target_asset.project_id,
            "Phase 3 relationships must stay within one Project.",
        )

    @staticmethod
    def _load_relationship_or_404(db: Session, relationship_id: str) -> AssetRelationship:
        relationship = db.scalar(
            select(AssetRelationship)
            .options(
                joinedload(AssetRelationship.source_asset).joinedload(Asset.project),
                joinedload(AssetRelationship.target_asset).joinedload(Asset.project),
            )
            .where(AssetRelationship.id == relationship_id)
        )
        if relationship is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Relationship not found.",
            )
        return relationship

    @staticmethod
    def _load_reference_or_404(db: Session, reference_id: str) -> AssetReference:
        reference = db.scalar(
            select(AssetReference)
            .options(joinedload(AssetReference.source_asset).joinedload(Asset.project))
            .where(AssetReference.id == reference_id)
        )
        if reference is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reference not found.",
            )
        return reference

    @staticmethod
    def _relationship_payload(relationship: AssetRelationship) -> dict[str, object]:
        return {
            "source_asset_id": relationship.source_asset_id,
            "target_asset_id": relationship.target_asset_id,
            "relationship_type": relationship.relationship_type,
            "direction": relationship.direction,
        }

    @staticmethod
    def _reference_payload(reference: AssetReference) -> dict[str, object]:
        return {
            "source_asset_id": reference.source_asset_id,
            "reference_type": reference.reference_type,
            "target_uri": reference.target_uri,
            "label": reference.label,
        }

    @staticmethod
    def _project_relationships(db: Session, *, project_id: str) -> list[AssetRelationship]:
        project_asset_ids = select(Asset.id).where(Asset.project_id == project_id)
        return list(
            db.scalars(
                select(AssetRelationship)
                .options(
                    joinedload(AssetRelationship.source_asset),
                    joinedload(AssetRelationship.target_asset),
                )
                .where(
                    and_(
                        AssetRelationship.source_asset_id.in_(project_asset_ids),
                        AssetRelationship.target_asset_id.in_(project_asset_ids),
                    )
                )
            )
        )

    @staticmethod
    def _outgoing_adjacency(
        relationships: list[AssetRelationship],
    ) -> dict[str, list[AssetRelationship]]:
        adjacency: dict[str, list[AssetRelationship]] = {}
        for relationship in relationships:
            adjacency.setdefault(relationship.source_asset_id, []).append(relationship)
        return adjacency

    @staticmethod
    def _path_exists(
        relationships: list[AssetRelationship],
        *,
        start_asset_id: str,
        target_asset_id: str,
        max_depth: int = MAX_GRAPH_DEPTH,
    ) -> bool:
        if start_asset_id == target_asset_id:
            return True
        adjacency = RelationshipsModule._outgoing_adjacency(relationships)
        queue: deque[tuple[str, int]] = deque([(start_asset_id, 0)])
        visited = {start_asset_id}
        while queue:
            current_asset_id, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for relationship in adjacency.get(current_asset_id, []):
                next_asset_id = relationship.target_asset_id
                if next_asset_id == target_asset_id:
                    return True
                if next_asset_id in visited:
                    continue
                visited.add(next_asset_id)
                queue.append((next_asset_id, depth + 1))
        return False

    @staticmethod
    def _detect_cycle(relationships: list[AssetRelationship]) -> bool:
        adjacency = RelationshipsModule._outgoing_adjacency(relationships)
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(asset_id: str) -> bool:
            if asset_id in visiting:
                return True
            if asset_id in visited:
                return False
            visiting.add(asset_id)
            for relationship in adjacency.get(asset_id, []):
                if visit(relationship.target_asset_id):
                    return True
            visiting.remove(asset_id)
            visited.add(asset_id)
            return False

        asset_ids = {relationship.source_asset_id for relationship in relationships} | {
            relationship.target_asset_id for relationship in relationships
        }
        return any(visit(asset_id) for asset_id in asset_ids)

    @staticmethod
    def _record_cycle_detection(
        db: Session,
        *,
        actor: User,
        relationship: AssetRelationship,
        project_id: str,
        organization_id: str,
    ) -> None:
        payload = {
            **RelationshipsModule._relationship_payload(relationship),
            "result": "detected",
        }
        record_audit(
            db,
            actor_user_id=actor.id,
            action="relationship.cycle_detected",
            resource_type="relationship",
            resource_id=relationship.id,
            organization_id=organization_id,
            project_id=project_id,
            details=payload,
        )
        emit_event(
            db,
            event_type="RelationshipCycleDetected",
            resource_type="relationship",
            resource_id=relationship.id,
            organization_id=organization_id,
            project_id=project_id,
            payload=payload,
        )

    @staticmethod
    @audited_phase3_mutation(
        event_type="RelationshipCreated",
        resource_type="relationship",
        source_asset_id="source_asset_id",
        target_asset_id="target_asset_id",
    )
    def create_relationship(
        db: Session,
        *,
        source_asset_id: str,
        target_asset_id: str,
        relationship_type: str,
        metadata: dict[str, object] | None,
        actor: User,
    ) -> AssetRelationship:
        source_asset = RelationshipsModule._get_asset(
            db,
            asset_id=source_asset_id,
            actor=actor,
            permission="update_asset",
        )
        target_asset = RelationshipsModule._get_asset(
            db,
            asset_id=target_asset_id,
            actor=actor,
            permission="read_project",
        )
        RelationshipsModule._require_same_project(source_asset, target_asset)
        require(
            source_asset.id != target_asset.id,
            "Self-relationships are not supported in Phase 3.",
        )
        normalized_type = RelationshipsModule._require_relationship_type(relationship_type)
        relationship_metadata = RelationshipsModule._normalize_metadata(metadata)
        existing = db.scalar(
            select(AssetRelationship).where(
                and_(
                    AssetRelationship.source_asset_id == source_asset.id,
                    AssetRelationship.target_asset_id == target_asset.id,
                    AssetRelationship.relationship_type == normalized_type,
                )
            )
        )
        require(
            existing is None,
            "Relationship already exists.",
            status.HTTP_409_CONFLICT,
        )
        relationship = AssetRelationship(
            source_asset_id=source_asset.id,
            target_asset_id=target_asset.id,
            relationship_type=normalized_type,
            direction=RELATIONSHIP_DIRECTION,
            metadata_json=relationship_metadata,
            created_by_user_id=actor.id,
        )
        db.add(relationship)
        source_asset.updated_at = utc_now()
        db.flush()
        payload = {
            **RelationshipsModule._relationship_payload(relationship),
            "metadata": relationship.metadata_json,
            "event_type": "RelationshipCreated",
            "relationship_id": relationship.id,
            "result": "success",
            "reason": None,
        }
        record_audit(
            db,
            actor_user_id=actor.id,
            action="relationship.created",
            resource_type="relationship",
            resource_id=relationship.id,
            organization_id=source_asset.project.organization_id,
            project_id=source_asset.project_id,
            details=payload,
        )
        emit_event(
            db,
            event_type="RelationshipCreated",
            resource_type="relationship",
            resource_id=relationship.id,
            organization_id=source_asset.project.organization_id,
            project_id=source_asset.project_id,
            payload=payload,
        )
        project_relationships = RelationshipsModule._project_relationships(
            db, project_id=source_asset.project_id
        )
        if RelationshipsModule._path_exists(
            project_relationships,
            start_asset_id=relationship.target_asset_id,
            target_asset_id=relationship.source_asset_id,
        ):
            RelationshipsModule._record_cycle_detection(
                db,
                actor=actor,
                relationship=relationship,
                project_id=source_asset.project_id,
                organization_id=source_asset.project.organization_id,
            )
        return relationship

    @staticmethod
    @audited_phase3_read(resource_type="relationship", source_asset_id="asset_id")
    def list_relationships(
        db: Session,
        *,
        asset_id: str,
        actor: User,
    ) -> list[AssetRelationship]:
        asset = RelationshipsModule._get_asset(db, asset_id=asset_id, actor=actor)
        statement = (
            select(AssetRelationship)
            .options(
                joinedload(AssetRelationship.source_asset),
                joinedload(AssetRelationship.target_asset),
            )
            .where(
                or_(
                    AssetRelationship.source_asset_id == asset.id,
                    AssetRelationship.target_asset_id == asset.id,
                )
            )
            .order_by(AssetRelationship.created_at.asc())
        )
        return list(db.scalars(statement))

    @staticmethod
    @audited_phase3_read(resource_type="relationship", source_asset_id="asset_id")
    def list_outgoing_relationships(
        db: Session,
        *,
        asset_id: str,
        actor: User,
    ) -> list[AssetRelationship]:
        asset = RelationshipsModule._get_asset(db, asset_id=asset_id, actor=actor)
        return list(
            db.scalars(
                select(AssetRelationship)
                .options(
                    joinedload(AssetRelationship.source_asset),
                    joinedload(AssetRelationship.target_asset),
                )
                .where(AssetRelationship.source_asset_id == asset.id)
                .order_by(AssetRelationship.created_at.asc())
            )
        )

    @staticmethod
    @audited_phase3_read(resource_type="relationship", source_asset_id="asset_id")
    def list_incoming_relationships(
        db: Session,
        *,
        asset_id: str,
        actor: User,
    ) -> list[AssetRelationship]:
        asset = RelationshipsModule._get_asset(db, asset_id=asset_id, actor=actor)
        return list(
            db.scalars(
                select(AssetRelationship)
                .options(
                    joinedload(AssetRelationship.source_asset),
                    joinedload(AssetRelationship.target_asset),
                )
                .where(AssetRelationship.target_asset_id == asset.id)
                .order_by(AssetRelationship.created_at.asc())
            )
        )

    @staticmethod
    @audited_phase3_mutation(
        event_type="RelationshipMetadataUpdated",
        resource_type="relationship",
        relationship_id="relationship_id",
    )
    def update_relationship_metadata(
        db: Session,
        *,
        relationship_id: str,
        metadata: dict[str, object] | None,
        actor: User,
    ) -> AssetRelationship:
        relationship = RelationshipsModule._load_relationship_or_404(db, relationship_id)
        source_asset = RelationshipsModule._get_asset(
            db,
            asset_id=relationship.source_asset_id,
            actor=actor,
            permission="update_asset",
        )
        relationship.metadata_json = RelationshipsModule._normalize_metadata(metadata)
        source_asset.updated_at = utc_now()
        payload = {
            **RelationshipsModule._relationship_payload(relationship),
            "metadata": relationship.metadata_json,
        }
        record_audit(
            db,
            actor_user_id=actor.id,
            action="relationship.metadata.updated",
            resource_type="relationship",
            resource_id=relationship.id,
            organization_id=source_asset.project.organization_id,
            project_id=source_asset.project_id,
            details=payload,
        )
        emit_event(
            db,
            event_type="RelationshipMetadataUpdated",
            resource_type="relationship",
            resource_id=relationship.id,
            organization_id=source_asset.project.organization_id,
            project_id=source_asset.project_id,
            payload=payload,
        )
        return relationship

    @staticmethod
    @audited_phase3_mutation(
        event_type="RelationshipDeleted",
        resource_type="relationship",
        relationship_id="relationship_id",
    )
    def delete_relationship(
        db: Session,
        *,
        relationship_id: str,
        actor: User,
    ) -> None:
        relationship = RelationshipsModule._load_relationship_or_404(db, relationship_id)
        source_asset = RelationshipsModule._get_asset(
            db,
            asset_id=relationship.source_asset_id,
            actor=actor,
            permission="update_asset",
        )
        payload = RelationshipsModule._relationship_payload(relationship)
        record_audit(
            db,
            actor_user_id=actor.id,
            action="relationship.deleted",
            resource_type="relationship",
            resource_id=relationship.id,
            organization_id=source_asset.project.organization_id,
            project_id=source_asset.project_id,
            details=payload,
        )
        emit_event(
            db,
            event_type="RelationshipDeleted",
            resource_type="relationship",
            resource_id=relationship.id,
            organization_id=source_asset.project.organization_id,
            project_id=source_asset.project_id,
            payload=payload,
        )
        source_asset.updated_at = utc_now()
        db.delete(relationship)

    @staticmethod
    @audited_phase3_mutation(
        event_type="ReferenceCreated",
        resource_type="reference",
        source_asset_id="source_asset_id",
        target_uri="target_uri",
    )
    def create_reference(
        db: Session,
        *,
        source_asset_id: str,
        reference_type: str,
        target_uri: str,
        label: str,
        metadata: dict[str, object] | None,
        actor: User,
    ) -> AssetReference:
        source_asset = RelationshipsModule._get_asset(
            db,
            asset_id=source_asset_id,
            actor=actor,
            permission="update_asset",
        )
        normalized_type = RelationshipsModule._require_reference_type(reference_type)
        normalized_uri = target_uri.strip()
        require(normalized_uri, "Reference target URI is required.")
        reference_metadata = RelationshipsModule._normalize_metadata(metadata)
        existing = db.scalar(
            select(AssetReference).where(
                and_(
                    AssetReference.source_asset_id == source_asset.id,
                    AssetReference.reference_type == normalized_type,
                    AssetReference.target_uri == normalized_uri,
                )
            )
        )
        require(existing is None, "Reference already exists.", status.HTTP_409_CONFLICT)
        reference = AssetReference(
            source_asset_id=source_asset.id,
            reference_type=normalized_type,
            target_uri=normalized_uri,
            label=label.strip(),
            metadata_json=reference_metadata,
            created_by_user_id=actor.id,
        )
        db.add(reference)
        source_asset.updated_at = utc_now()
        db.flush()
        payload = {
            **RelationshipsModule._reference_payload(reference),
            "metadata": reference.metadata_json,
        }
        record_audit(
            db,
            actor_user_id=actor.id,
            action="reference.created",
            resource_type="reference",
            resource_id=reference.id,
            organization_id=source_asset.project.organization_id,
            project_id=source_asset.project_id,
            details=payload,
        )
        emit_event(
            db,
            event_type="ReferenceCreated",
            resource_type="reference",
            resource_id=reference.id,
            organization_id=source_asset.project.organization_id,
            project_id=source_asset.project_id,
            payload=payload,
        )
        return reference

    @staticmethod
    @audited_phase3_read(resource_type="reference", source_asset_id="asset_id")
    def list_references(
        db: Session,
        *,
        asset_id: str,
        actor: User,
    ) -> list[AssetReference]:
        asset = RelationshipsModule._get_asset(db, asset_id=asset_id, actor=actor)
        return list(
            db.scalars(
                select(AssetReference)
                .options(joinedload(AssetReference.source_asset))
                .where(AssetReference.source_asset_id == asset.id)
                .order_by(AssetReference.created_at.asc())
            )
        )

    @staticmethod
    @audited_phase3_mutation(
        event_type="ReferenceDeleted",
        resource_type="reference",
        reference_id="reference_id",
    )
    def delete_reference(
        db: Session,
        *,
        reference_id: str,
        actor: User,
    ) -> None:
        reference = RelationshipsModule._load_reference_or_404(db, reference_id)
        source_asset = RelationshipsModule._get_asset(
            db,
            asset_id=reference.source_asset_id,
            actor=actor,
            permission="update_asset",
        )
        payload = RelationshipsModule._reference_payload(reference)
        record_audit(
            db,
            actor_user_id=actor.id,
            action="reference.deleted",
            resource_type="reference",
            resource_id=reference.id,
            organization_id=source_asset.project.organization_id,
            project_id=source_asset.project_id,
            details=payload,
        )
        emit_event(
            db,
            event_type="ReferenceDeleted",
            resource_type="reference",
            resource_id=reference.id,
            organization_id=source_asset.project.organization_id,
            project_id=source_asset.project_id,
            payload=payload,
        )
        source_asset.updated_at = utc_now()
        db.delete(reference)

    @staticmethod
    @audited_phase3_mutation(
        event_type="ReferenceResolved",
        resource_type="reference",
        reference_id="reference_id",
        target_asset_id="target_asset_id",
    )
    def resolve_reference(
        db: Session,
        *,
        reference_id: str,
        target_asset_id: str,
        relationship_type: str,
        actor: User,
    ) -> AssetRelationship:
        reference = RelationshipsModule._load_reference_or_404(db, reference_id)
        source_asset = RelationshipsModule._get_asset(
            db,
            asset_id=reference.source_asset_id,
            actor=actor,
            permission="update_asset",
        )
        relationship = RelationshipsModule.create_relationship(
            db,
            source_asset_id=reference.source_asset_id,
            target_asset_id=target_asset_id,
            relationship_type=relationship_type,
            metadata={"resolved_from_reference_id": reference.id},
            actor=actor,
        )
        payload = {
            **RelationshipsModule._reference_payload(reference),
            "resolved_relationship_id": relationship.id,
            "target_asset_id": relationship.target_asset_id,
            "relationship_type": relationship.relationship_type,
        }
        record_audit(
            db,
            actor_user_id=actor.id,
            action="reference.resolved",
            resource_type="reference",
            resource_id=reference.id,
            organization_id=source_asset.project.organization_id,
            project_id=source_asset.project_id,
            details=payload,
        )
        emit_event(
            db,
            event_type="ReferenceResolved",
            resource_type="reference",
            resource_id=reference.id,
            organization_id=source_asset.project.organization_id,
            project_id=source_asset.project_id,
            payload=payload,
        )
        source_asset.updated_at = utc_now()
        db.delete(reference)
        return relationship

    @staticmethod
    @audited_phase3_read(resource_type="graph", source_asset_id="asset_id")
    def get_graph(
        db: Session,
        *,
        asset_id: str,
        actor: User,
        direction: str = "outgoing",
        max_depth: int = DEFAULT_GRAPH_DEPTH,
        target_asset_id: str | None = None,
    ) -> GraphQueryResult:
        root_asset = RelationshipsModule._get_asset(db, asset_id=asset_id, actor=actor)
        require(direction in GRAPH_DIRECTIONS, "Invalid graph direction.")
        require(max_depth >= 1, "Graph depth must be at least 1.")
        require(
            max_depth <= MAX_GRAPH_DEPTH,
            f"Graph depth cannot exceed {MAX_GRAPH_DEPTH}.",
        )
        target_asset: Asset | None = None
        if target_asset_id is not None:
            target_asset = RelationshipsModule._get_asset(
                db,
                asset_id=target_asset_id,
                actor=actor,
            )
            RelationshipsModule._require_same_project(root_asset, target_asset)

        project_relationships = RelationshipsModule._project_relationships(
            db, project_id=root_asset.project_id
        )
        outgoing = RelationshipsModule._outgoing_adjacency(project_relationships)
        incoming: dict[str, list[AssetRelationship]] = {}
        asset_by_id: dict[str, Asset] = {root_asset.id: root_asset}
        for relationship in project_relationships:
            incoming.setdefault(relationship.target_asset_id, []).append(relationship)
            if relationship.source_asset is not None:
                asset_by_id[relationship.source_asset_id] = relationship.source_asset
            if relationship.target_asset is not None:
                asset_by_id[relationship.target_asset_id] = relationship.target_asset

        queue: deque[tuple[str, int]] = deque([(root_asset.id, 0)])
        visited_nodes = {root_asset.id}
        seen_relationship_ids: set[str] = set()
        traversed_relationships: list[AssetRelationship] = []
        while queue:
            current_asset_id, depth = queue.popleft()
            if depth >= max_depth:
                continue
            edge_candidates: list[tuple[AssetRelationship, str]] = []
            if direction in {"outgoing", "both"}:
                edge_candidates.extend(
                    (relationship, relationship.target_asset_id)
                    for relationship in outgoing.get(current_asset_id, [])
                )
            if direction in {"incoming", "both"}:
                edge_candidates.extend(
                    (relationship, relationship.source_asset_id)
                    for relationship in incoming.get(current_asset_id, [])
                )
            for relationship, next_asset_id in edge_candidates:
                if relationship.id not in seen_relationship_ids:
                    seen_relationship_ids.add(relationship.id)
                    traversed_relationships.append(relationship)
                if next_asset_id in visited_nodes:
                    continue
                visited_nodes.add(next_asset_id)
                queue.append((next_asset_id, depth + 1))

        traversed_nodes = [
            asset
            for asset_id_value, asset in asset_by_id.items()
            if asset_id_value in visited_nodes
        ]
        path_exists = None
        if target_asset is not None:
            path_exists = target_asset.id in visited_nodes
        has_cycle = RelationshipsModule._detect_cycle(traversed_relationships)
        result = GraphQueryResult(
            root_asset=root_asset,
            direction=direction,
            max_depth=max_depth,
            target_asset_id=target_asset.id if target_asset is not None else None,
            path_exists=path_exists,
            has_cycle=has_cycle,
            nodes=traversed_nodes,
            relationships=traversed_relationships,
        )
        if Settings().audit_graph_queries and _AUDIT_EVENTS is not None:
            audit_context = Phase3AuditContext(
                actor_user_id=actor.id,
                event_type="GraphQueryExecuted",
                resource_type="graph",
                resource_id=root_asset.id,
                project_id=root_asset.project_id,
                organization_id=root_asset.project.organization_id,
                source_asset_id=root_asset.id,
                target_asset_id=target_asset.id if target_asset is not None else None,
            )
            _AUDIT_EVENTS.record_phase3_outcome(
                db,
                context=audit_context,
                outcome=AuditOutcome("success"),
            )
            _AUDIT_EVENTS.emit_domain_event(
                db,
                context=audit_context,
                payload={"direction": direction, "max_depth": max_depth},
            )
        return result


class CollaborationModule:
    """Public collaboration module service for Phase 2."""

    @staticmethod
    def _observability_payload(
        *,
        result: str,
        reason: str | None = None,
        error: str | None = None,
        details: dict[str, object] | None = None,
    ) -> dict[str, object]:
        payload = dict(details or {})
        payload["result"] = result
        if reason is not None:
            payload["reason"] = reason
        if error is not None:
            payload["error"] = error
        return payload

    @staticmethod
    def _get_asset_for_collaboration(db: Session, *, asset_id: str, actor: User) -> Asset:
        return db.scalar(
            select(Asset)
            .options(
                joinedload(Asset.project),
                joinedload(Asset.collaboration_lock).joinedload(AssetCollaborationLock.owner),
                joinedload(Asset.revisions)
                .joinedload(Revision.representations)
                .joinedload(Representation.blob),
            )
            .where(Asset.id == asset_id)
        ) or AssetsModule.get_asset(db, asset_id=asset_id, actor=actor)

    @staticmethod
    def _get_project_role(db: Session, *, project_id: str, user_id: str) -> str | None:
        return ProjectModule.check_project_role(db, project_id=project_id, user_id=user_id)

    @staticmethod
    def _resolve_state(db: Session, asset: Asset) -> str:
        lock = asset.collaboration_lock
        if lock is None:
            return "available"
        org_role = _membership_role(
            db,
            model=OrganizationMembership,
            field_name="organization_id",
            parent_id=asset.project.organization_id,
            user_id=lock.owner_user_id,
        )
        project_role = CollaborationModule._get_project_role(
            db, project_id=asset.project_id, user_id=lock.owner_user_id
        )
        if (
            asset.status == "archived"
            or not lock.owner.is_active
            or org_role is None
            or project_role not in LOCK_OWNER_WRITE_ROLES
        ):
            return "stale_lock"
        return "locked"

    @staticmethod
    def get_collaboration_state(db: Session, *, asset_id: str, actor: User) -> CollaborationState:
        asset = CollaborationModule._get_asset_for_collaboration(db, asset_id=asset_id, actor=actor)
        ProjectModule.require_project_permission(
            db, project_id=asset.project_id, actor=actor, permission="read_project"
        )
        project_role = CollaborationModule._get_project_role(
            db, project_id=asset.project_id, user_id=actor.id
        )
        state = CollaborationModule._resolve_state(db, asset)
        lock = asset.collaboration_lock
        is_owner = lock is not None and lock.owner_user_id == actor.id
        can_force_unlock = project_role in FORCE_UNLOCK_ROLES and lock is not None and not is_owner
        return CollaborationState(
            asset=asset,
            state=state,
            lock=lock,
            project_role=project_role,
            can_checkin=is_owner and state == "locked",
            can_unlock=is_owner and state in {"locked", "stale_lock"},
            can_force_unlock=can_force_unlock,
        )

    @staticmethod
    def _record_conflict(
        db: Session,
        *,
        actor: User,
        asset: Asset,
        code: str,
        message: str,
        details: dict[str, object] | None = None,
        status_code: int = status.HTTP_409_CONFLICT,
    ) -> None:
        recovery = collaboration_recovery_context(code, details=details)
        payload = CollaborationModule._observability_payload(
            result="rejected",
            reason=code,
            error=message,
            details={"code": code, **recovery},
        )
        record_audit(
            db,
            actor_user_id=actor.id,
            action="collaboration.conflict_detected",
            resource_type="asset",
            resource_id=asset.id,
            organization_id=asset.project.organization_id,
            project_id=asset.project_id,
            details=payload,
        )
        emit_event(
            db,
            event_type="collaboration.conflict_detected",
            resource_type="asset",
            resource_id=asset.id,
            organization_id=asset.project.organization_id,
            project_id=asset.project_id,
            payload=payload,
        )
        NotificationsModule.notify_project_members(
            db,
            organization_id=asset.project.organization_id,
            project_id=asset.project_id,
            asset_id=asset.id,
            revision_id=None,
            event_type="collaboration.conflict_detected",
            actor_user_id=actor.id,
            details=payload,
            include_actor=True,
            recipient_user_ids=[actor.id],
        )
        db.commit()
        raise collaboration_error(
            code=code, message=message, status_code=status_code, context=payload
        )

    @staticmethod
    def _record_failed_checkin(
        db: Session,
        *,
        actor: User,
        asset: Asset,
        code: str,
        message: str,
        details: dict[str, object] | None = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        emit_conflict: bool = False,
    ) -> None:
        payload = CollaborationModule._observability_payload(
            result="failed",
            reason=code,
            error=message,
            details={"code": code, **collaboration_recovery_context(code, details=details)},
        )
        record_audit(
            db,
            actor_user_id=actor.id,
            action="asset.checkin_failed",
            resource_type="asset",
            resource_id=asset.id,
            organization_id=asset.project.organization_id,
            project_id=asset.project_id,
            details=payload,
        )
        emit_event(
            db,
            event_type="asset.checkin_failed",
            resource_type="asset",
            resource_id=asset.id,
            organization_id=asset.project.organization_id,
            project_id=asset.project_id,
            payload=payload,
        )
        if emit_conflict:
            record_audit(
                db,
                actor_user_id=actor.id,
                action="collaboration.conflict_detected",
                resource_type="asset",
                resource_id=asset.id,
                organization_id=asset.project.organization_id,
                project_id=asset.project_id,
                details=payload,
            )
            emit_event(
                db,
                event_type="collaboration.conflict_detected",
                resource_type="asset",
                resource_id=asset.id,
                organization_id=asset.project.organization_id,
                project_id=asset.project_id,
                payload=payload,
            )
            NotificationsModule.notify_project_members(
                db,
                organization_id=asset.project.organization_id,
                project_id=asset.project_id,
                asset_id=asset.id,
                revision_id=None,
                event_type="collaboration.conflict_detected",
                actor_user_id=actor.id,
                details=payload,
                include_actor=True,
                recipient_user_ids=[actor.id],
            )
        db.commit()
        raise collaboration_error(
            code=code, message=message, status_code=status_code, context=payload
        )

    @staticmethod
    def _validate_checkin_representations(
        db: Session, *, asset: Asset, representations: list[dict[str, object]], actor: User
    ) -> None:
        for item in representations:
            blob_id = item.get("blob_id")
            if blob_id is None:
                continue
            blob = db.get(Blob, str(blob_id))
            if blob is None:
                CollaborationModule._record_failed_checkin(
                    db,
                    actor=actor,
                    asset=asset,
                    code="representation_blob_not_found",
                    message="Referenced Blob does not exist for check-in.",
                    details={"blob_id": str(blob_id)},
                    status_code=status.HTTP_404_NOT_FOUND,
                )

    @staticmethod
    def checkout(db: Session, *, asset_id: str, actor: User) -> CollaborationState:
        state = CollaborationModule.get_collaboration_state(db, asset_id=asset_id, actor=actor)
        asset = state.asset
        ProjectModule.require_project_permission(
            db, project_id=asset.project_id, actor=actor, permission="update_asset"
        )
        if asset.status == "archived":
            CollaborationModule._record_conflict(
                db,
                actor=actor,
                asset=asset,
                code="asset_archived",
                message="Archived Assets cannot be checked out.",
            )
        lock = asset.collaboration_lock
        if lock is not None and lock.owner_user_id == actor.id:
            return state
        if lock is not None:
            CollaborationModule._record_conflict(
                db,
                actor=actor,
                asset=asset,
                code="asset_locked",
                message="Asset is already locked by another user.",
                details={"lock_owner_user_id": lock.owner_user_id},
            )
        lock = AssetCollaborationLock(asset_id=asset.id, owner_user_id=actor.id)
        db.add(lock)
        db.flush()
        record_audit(
            db,
            actor_user_id=actor.id,
            action="asset.checked_out",
            resource_type="asset",
            resource_id=asset.id,
            organization_id=asset.project.organization_id,
            project_id=asset.project_id,
            details=CollaborationModule._observability_payload(
                result="succeeded", details={"lock_owner_user_id": actor.id}
            ),
        )
        emit_event(
            db,
            event_type="asset.checked_out",
            resource_type="asset",
            resource_id=asset.id,
            organization_id=asset.project.organization_id,
            project_id=asset.project_id,
            payload=CollaborationModule._observability_payload(
                result="succeeded", details={"lock_owner_user_id": actor.id}
            ),
        )
        NotificationsModule.notify_project_members(
            db,
            organization_id=asset.project.organization_id,
            project_id=asset.project_id,
            asset_id=asset.id,
            revision_id=None,
            event_type="asset.checked_out",
            actor_user_id=actor.id,
            details={"lock_owner_user_id": actor.id},
        )
        db.refresh(asset)
        return CollaborationModule.get_collaboration_state(db, asset_id=asset_id, actor=actor)

    @staticmethod
    def unlock(
        db: Session, *, asset_id: str, actor: User, force: bool = False
    ) -> CollaborationState:
        state = CollaborationModule.get_collaboration_state(db, asset_id=asset_id, actor=actor)
        asset = state.asset
        lock = state.lock
        if lock is None:
            CollaborationModule._record_conflict(
                db,
                actor=actor,
                asset=asset,
                code="no_active_lock",
                message="Asset does not have an active collaboration lock.",
            )
        is_owner = lock.owner_user_id == actor.id
        can_force = state.project_role in FORCE_UNLOCK_ROLES
        if not is_owner and not (force and can_force):
            CollaborationModule._record_conflict(
                db,
                actor=actor,
                asset=asset,
                code="unlock_not_allowed",
                message="Only the lock owner can unlock unless a Maintainer or Owner force-unlocks.",
                details={"lock_owner_user_id": lock.owner_user_id},
                status_code=status.HTTP_403_FORBIDDEN,
            )
        action = "asset.force_unlocked" if not is_owner else "asset.unlocked"
        payload = CollaborationModule._observability_payload(
            result="succeeded", details={"lock_owner_user_id": lock.owner_user_id}
        )
        record_audit(
            db,
            actor_user_id=actor.id,
            action=action,
            resource_type="asset",
            resource_id=asset.id,
            organization_id=asset.project.organization_id,
            project_id=asset.project_id,
            details=payload,
        )
        emit_event(
            db,
            event_type=action,
            resource_type="asset",
            resource_id=asset.id,
            organization_id=asset.project.organization_id,
            project_id=asset.project_id,
            payload=payload,
        )
        NotificationsModule.notify_project_members(
            db,
            organization_id=asset.project.organization_id,
            project_id=asset.project_id,
            asset_id=asset.id,
            revision_id=None,
            event_type=action,
            actor_user_id=actor.id,
            details={"lock_owner_user_id": lock.owner_user_id},
        )
        db.delete(lock)
        db.flush()
        db.expire(asset, ["collaboration_lock"])
        return CollaborationModule.get_collaboration_state(db, asset_id=asset_id, actor=actor)

    @staticmethod
    def checkin(
        db: Session,
        *,
        asset_id: str,
        comment: str,
        representations: list[dict[str, object]],
        actor: User,
    ) -> Revision:
        state = CollaborationModule.get_collaboration_state(db, asset_id=asset_id, actor=actor)
        asset = state.asset
        lock = state.lock
        if not comment.strip():
            CollaborationModule._record_failed_checkin(
                db,
                actor=actor,
                asset=asset,
                code="checkin_comment_required",
                message="Check-in comment is required.",
            )
        if asset.status == "archived":
            CollaborationModule._record_failed_checkin(
                db,
                actor=actor,
                asset=asset,
                code="asset_archived",
                message="Archived Assets cannot be checked in.",
                status_code=status.HTTP_409_CONFLICT,
                emit_conflict=True,
            )
        if lock is None:
            CollaborationModule._record_failed_checkin(
                db,
                actor=actor,
                asset=asset,
                code="checkin_without_lock",
                message="Asset must be checked out before check-in.",
                status_code=status.HTTP_409_CONFLICT,
                emit_conflict=True,
            )
        if lock.owner_user_id != actor.id:
            CollaborationModule._record_failed_checkin(
                db,
                actor=actor,
                asset=asset,
                code="checkin_by_non_owner",
                message="Only the lock owner can check in changes.",
                details={"lock_owner_user_id": lock.owner_user_id},
                status_code=status.HTTP_409_CONFLICT,
                emit_conflict=True,
            )
        CollaborationModule._validate_checkin_representations(
            db, asset=asset, representations=representations, actor=actor
        )
        revision = AssetsModule.create_revision(db, asset_id=asset.id, comment=comment, actor=actor)
        for item in representations:
            AssetsModule.add_representation(
                db,
                revision_id=revision.id,
                name=str(item["name"]),
                media_type=str(item["media_type"]),
                blob_id=str(item["blob_id"]) if item.get("blob_id") is not None else None,
                actor=actor,
            )
        payload = CollaborationModule._observability_payload(
            result="succeeded",
            details={"revision_id": revision.id, "revision_number": revision.number},
        )
        record_audit(
            db,
            actor_user_id=actor.id,
            action="asset.checked_in",
            resource_type="asset",
            resource_id=asset.id,
            organization_id=asset.project.organization_id,
            project_id=asset.project_id,
            details=payload,
        )
        emit_event(
            db,
            event_type="asset.checked_in",
            resource_type="asset",
            resource_id=asset.id,
            organization_id=asset.project.organization_id,
            project_id=asset.project_id,
            payload=payload,
        )
        db.delete(lock)
        db.flush()
        db.expire(asset, ["collaboration_lock"])
        return (
            db.scalar(
                select(Revision)
                .options(joinedload(Revision.representations).joinedload(Representation.blob))
                .where(Revision.id == revision.id)
            )
            or revision
        )

    @staticmethod
    def list_timeline(db: Session, *, asset_id: str, actor: User) -> list[TimelineEntry]:
        asset = AssetsModule.get_asset(db, asset_id=asset_id, actor=actor)
        records = list(
            db.scalars(
                select(AuditRecord)
                .where(
                    and_(
                        AuditRecord.project_id == asset.project_id,
                        AuditRecord.action.in_(tuple(TIMELINE_EVENT_MAP.keys())),
                    )
                )
                .order_by(AuditRecord.occurred_at.desc())
            )
        )
        entries: list[TimelineEntry] = []
        for record in records:
            details = dict(record.details or {})
            is_asset_event = record.resource_type == "asset" and record.resource_id == asset.id
            is_revision_event = (
                record.action == "revision.created" and str(details.get("asset_id")) == asset.id
            )
            if not (is_asset_event or is_revision_event):
                continue
            revision_id = details.get("revision_id")
            if revision_id is not None:
                revision_id = str(revision_id)
            entries.append(
                TimelineEntry(
                    event_type=TIMELINE_EVENT_MAP[record.action],
                    occurred_at=record.occurred_at,
                    actor_user_id=record.actor_user_id,
                    asset_id=asset.id,
                    revision_id=revision_id,
                    details=details,
                )
            )
        return entries


class MetadataModule:
    """Public Metadata module service."""

    @staticmethod
    def _validate_target(
        db: Session,
        *,
        target_type: str,
        target_id: str,
        actor: User,
    ) -> tuple[str | None, str | None]:
        if target_type == "asset":
            asset = AssetsModule.get_asset(db, asset_id=target_id, actor=actor)
            return asset.project.organization_id, asset.project_id
        if target_type == "revision":
            revision = db.scalar(
                select(Revision)
                .options(joinedload(Revision.asset).joinedload(Asset.project))
                .where(Revision.id == target_id)
            )
            if revision is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Revision not found.",
                )
            ProjectModule.require_project_permission(
                db, project_id=revision.asset.project_id, actor=actor, permission="read_project"
            )
            return revision.asset.project.organization_id, revision.asset.project_id
        if target_type == "representation":
            representation = db.scalar(
                select(Representation)
                .options(
                    joinedload(Representation.revision)
                    .joinedload(Revision.asset)
                    .joinedload(Asset.project)
                )
                .where(Representation.id == target_id)
            )
            if representation is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Representation not found.",
                )
            ProjectModule.require_project_permission(
                db,
                project_id=representation.revision.asset.project_id,
                actor=actor,
                permission="read_project",
            )
            return (
                representation.revision.asset.project.organization_id,
                representation.revision.asset.project_id,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid metadata target type.",
        )

    @staticmethod
    def put_entry(
        db: Session,
        *,
        target_type: str,
        target_id: str,
        key: str,
        value: object,
        value_type: str,
        source: str,
        actor: User,
    ) -> MetadataEntry:
        organization_id, project_id = MetadataModule._validate_target(
            db, target_type=target_type, target_id=target_id, actor=actor
        )
        if project_id is not None:
            ProjectModule.require_project_permission(
                db,
                project_id=project_id,
                actor=actor,
                permission="update_asset",
            )
        require(value_type in ALLOWED_METADATA_TYPES, "Invalid metadata value type.")
        field_name = METADATA_TARGET_FIELDS[target_type]
        target_field = getattr(MetadataEntry, field_name)
        filters = [
            target_field == target_id,
            MetadataEntry.key == key.strip(),
            MetadataEntry.source == source.strip(),
        ]
        existing = db.scalars(select(MetadataEntry).where(and_(*filters))).all()
        for item in existing:
            db.delete(item)
        entry = MetadataEntry(
            key=key.strip(),
            value=value,
            value_type=value_type,
            source=source.strip(),
            **{field_name: target_id},
        )
        db.add(entry)
        db.flush()
        record_audit(
            db,
            actor_user_id=actor.id,
            action="metadata.upserted",
            resource_type="metadata_entry",
            resource_id=entry.id,
            organization_id=organization_id,
            project_id=project_id,
            details={"target_type": target_type, "target_id": target_id, "key": key.strip()},
        )
        emit_event(
            db,
            event_type="metadata.upserted",
            resource_type="metadata_entry",
            resource_id=entry.id,
            organization_id=organization_id,
            project_id=project_id,
            payload={"target_type": target_type, "target_id": target_id, "key": key.strip()},
        )
        return entry

    @staticmethod
    def list_entries(
        db: Session,
        *,
        target_type: str,
        target_id: str,
        actor: User,
    ) -> list[MetadataEntry]:
        MetadataModule._validate_target(
            db, target_type=target_type, target_id=target_id, actor=actor
        )
        field_name = METADATA_TARGET_FIELDS[target_type]
        target_field = getattr(MetadataEntry, field_name)
        return list(db.scalars(select(MetadataEntry).where(target_field == target_id)))


class SearchModule:
    """Public Search module service."""

    @staticmethod
    def search_assets(
        db: Session,
        *,
        query_text: str,
        actor: User,
        organization_id: str | None = None,
        project_id: str | None = None,
    ) -> list[Asset]:
        normalized = query_text.strip()
        require(normalized, "Search query is required.")

        stmt = (
            select(Asset)
            .join(Project, Project.id == Asset.project_id)
            .join(ProjectMembership, ProjectMembership.project_id == Project.id)
            .outerjoin(Revision, Revision.asset_id == Asset.id)
            .where(ProjectMembership.user_id == actor.id)
            .outerjoin(
                MetadataEntry,
                or_(
                    MetadataEntry.asset_id == Asset.id,
                    MetadataEntry.revision_id == Revision.id,
                ),
            )
        )

        if organization_id is not None:
            stmt = stmt.where(Project.organization_id == organization_id)
        if project_id is not None:
            stmt = stmt.where(Project.id == project_id)

        dialect_name = db.get_bind().dialect.name
        if dialect_name == "postgresql":
            vector = func.to_tsvector(
                literal("simple"),
                func.concat_ws(
                    literal(" "),
                    Asset.name,
                    Asset.description,
                    MetadataEntry.key,
                    cast(MetadataEntry.value, String),
                    Revision.comment,
                ),
            )
            predicate = vector.op("@@")(func.plainto_tsquery(literal("simple"), normalized))
        else:
            pattern = f"%{normalized.lower()}%"
            predicate = or_(
                func.lower(Asset.name).like(pattern),
                func.lower(Asset.description).like(pattern),
                func.lower(func.coalesce(MetadataEntry.key, "")).like(pattern),
                func.lower(cast(func.coalesce(MetadataEntry.value, literal("")), String)).like(
                    pattern
                ),
                func.lower(func.coalesce(Revision.comment, "")).like(pattern),
            )

        return list(db.scalars(stmt.where(predicate).distinct().order_by(Asset.updated_at.desc())))


class PluginsModule:
    """Public Plugins Platform Module lifecycle service."""

    @staticmethod
    def require_platform_admin(actor: User) -> None:
        require(
            actor.is_active and actor.is_platform_admin,
            "Platform Administrator authority is required.",
            status.HTTP_403_FORBIDDEN,
        )

    @staticmethod
    def register_plugin(
        db: Session,
        *,
        plugin_id: str,
        name: str,
        version: str,
        plugin_type: str,
        capabilities: list[str],
        actor: User,
    ) -> PluginRecord:
        """Legacy metadata-only registration is not a supported Phase 4 installation path."""
        PluginsModule.require_platform_admin(actor)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Install a validated OpenPDM plugin package instead of registering metadata.",
        )

    @staticmethod
    def install_package(
        db: Session,
        *,
        package: ValidatedPluginPackage,
        package_storage: PluginPackageStorage,
        plugin_type: str,
        actor: User,
        discovered_only: bool = False,
        expected_plugin_id: str | None = None,
    ) -> PluginRecord:
        PluginsModule.require_platform_admin(actor)
        require(plugin_type in ALLOWED_PLUGIN_TYPES, "Invalid plugin type.")
        manifest = package.manifest
        existing = db.get(PluginRecord, manifest.id)
        if expected_plugin_id is not None:
            require(
                manifest.id == expected_plugin_id,
                "Upgrade package identity does not match the installed plugin.",
            )
            require(existing is not None, "Plugin not found.", status.HTTP_404_NOT_FOUND)
            require(
                not existing.enabled,
                "Disable the plugin before upgrade.",
                status.HTTP_409_CONFLICT,
            )
        else:
            require(existing is None, "Plugin is already installed.", status.HTTP_409_CONFLICT)
        package_storage.put(package.digest, package.archive)
        lifecycle_state = (
            "incompatible"
            if not manifest.is_compatible
            else "discovered"
            if discovered_only
            else "installed"
        )
        diagnostic_reason = (
            "Plugin does not support Extension API v1."
            if lifecycle_state == "incompatible"
            else None
        )
        action = (
            "plugin.upgraded"
            if existing is not None
            else "plugin.discovered"
            if discovered_only
            else "plugin.installed"
        )
        plugin = existing or PluginRecord(id=manifest.id)
        plugin.name = manifest.name
        plugin.version = manifest.version
        plugin.plugin_type = plugin_type
        plugin.capabilities = [capability.value for capability in manifest.capabilities]
        plugin.event_subscriptions = manifest.event_subscriptions
        plugin.configuration_schema = (
            manifest.configuration.model_dump(mode="json")
            if manifest.configuration is not None
            else None
        )
        plugin.extension_api_versions = manifest.extension_api_versions
        plugin.component = manifest.component
        plugin.package_digest = package.digest
        plugin.lifecycle_state = lifecycle_state
        plugin.diagnostic_reason = diagnostic_reason
        plugin.installed_by_user_id = actor.id
        plugin.enabled = False
        plugin.updated_at = utc_now()
        if existing is None:
            db.add(plugin)
        else:
            configuration = db.get(PluginConfiguration, plugin.id)
            if configuration is not None:
                db.delete(configuration)
        db.flush()
        record_audit(
            db,
            actor_user_id=actor.id,
            action=action,
            resource_type="plugin",
            resource_id=plugin.id,
            details={
                "version": plugin.version,
                "package_digest": plugin.package_digest,
                "plugin_type": plugin.plugin_type,
                "lifecycle_state": plugin.lifecycle_state,
            },
        )
        emit_event(
            db,
            event_type=action,
            resource_type="plugin",
            resource_id=plugin.id,
            payload={"version": plugin.version, "package_digest": plugin.package_digest},
        )
        return plugin

    @staticmethod
    def promote_discovered_plugin(db: Session, *, plugin_id: str, actor: User) -> PluginRecord:
        PluginsModule.require_platform_admin(actor)
        plugin = PluginsModule.get_plugin(db, plugin_id=plugin_id, actor=actor)
        require(
            plugin.lifecycle_state == "discovered",
            "Only a compatible discovered plugin can be installed.",
            status.HTTP_409_CONFLICT,
        )
        plugin.lifecycle_state = "installed"
        plugin.updated_at = utc_now()
        record_audit(
            db,
            actor_user_id=actor.id,
            action="plugin.installed",
            resource_type="plugin",
            resource_id=plugin.id,
            details={"version": plugin.version, "package_digest": plugin.package_digest},
        )
        emit_event(
            db,
            event_type="plugin.installed",
            resource_type="plugin",
            resource_id=plugin.id,
            payload={"version": plugin.version, "package_digest": plugin.package_digest},
        )
        return plugin

    @staticmethod
    def remove_plugin(db: Session, *, plugin_id: str, actor: User) -> None:
        PluginsModule.require_platform_admin(actor)
        plugin = PluginsModule.get_plugin(db, plugin_id=plugin_id, actor=actor)
        require(not plugin.enabled, "Disable the plugin before removal.", status.HTTP_409_CONFLICT)
        details = {"version": plugin.version, "package_digest": plugin.package_digest}
        db.execute(delete(PluginEventDelivery).where(PluginEventDelivery.plugin_id == plugin.id))
        configuration = db.get(PluginConfiguration, plugin.id)
        if configuration is not None:
            db.delete(configuration)
        db.delete(plugin)
        record_audit(
            db,
            actor_user_id=actor.id,
            action="plugin.removed",
            resource_type="plugin",
            resource_id=plugin.id,
            details=details,
        )
        emit_event(
            db,
            event_type="plugin.removed",
            resource_type="plugin",
            resource_id=plugin.id,
            payload=details,
        )

    @staticmethod
    def get_configuration(
        db: Session, *, plugin_id: str, actor: User
    ) -> tuple[PluginRecord, PluginConfiguration | None]:
        PluginsModule.require_platform_admin(actor)
        plugin = PluginsModule.get_plugin(db, plugin_id=plugin_id, actor=actor)
        return plugin, db.get(PluginConfiguration, plugin_id)

    @staticmethod
    def get_runtime_configuration(
        db: Session, *, plugin_id: str, cipher: PluginSecretCipher
    ) -> dict[str, object]:
        configuration = db.get(PluginConfiguration, plugin_id)
        if configuration is None:
            return {}
        return {
            **configuration.public_values,
            **cipher.decrypt(configuration.encrypted_secrets),
        }

    @staticmethod
    def set_configuration(
        db: Session,
        *,
        plugin_id: str,
        values: dict[str, object],
        actor: User,
        cipher: PluginSecretCipher,
    ) -> PluginConfiguration:
        PluginsModule.require_platform_admin(actor)
        plugin = PluginsModule.get_plugin(db, plugin_id=plugin_id, actor=actor)
        schema = plugin.configuration_schema
        require(schema is not None, "Plugin does not declare configuration.")
        properties = type_cast(dict[str, dict[str, object]], schema.get("properties", {}))
        required = set(type_cast(list[str], schema.get("required", [])))
        unknown = sorted(set(values) - set(properties))
        require(not unknown, f"Unknown plugin configuration properties: {', '.join(unknown)}")

        existing = db.get(PluginConfiguration, plugin_id)
        existing_secrets = cipher.decrypt(existing.encrypted_secrets) if existing else {}
        public_values: dict[str, object] = {}
        secret_values = dict(existing_secrets)
        for key, value in values.items():
            property_schema = properties[key]
            expected_type = type_cast(str, property_schema["type"])
            valid = {
                "string": isinstance(value, str),
                "number": isinstance(value, int | float) and not isinstance(value, bool),
                "integer": isinstance(value, int) and not isinstance(value, bool),
                "boolean": isinstance(value, bool),
            }[expected_type]
            require(valid, f"Invalid value type for plugin configuration property {key!r}.")
            if property_schema.get("secret") is True:
                secret_values[key] = value
            else:
                public_values[key] = value
        if existing:
            for key, value in existing.public_values.items():
                if key not in values:
                    public_values[key] = value
        missing = sorted(
            key for key in required if key not in public_values and key not in secret_values
        )
        require(not missing, f"Missing required plugin configuration: {', '.join(missing)}")

        encrypted = cipher.encrypt(secret_values)
        if existing is None:
            existing = PluginConfiguration(
                plugin_id=plugin.id,
                public_values=public_values,
                encrypted_secrets=encrypted,
                updated_by_user_id=actor.id,
            )
            db.add(existing)
        else:
            existing.public_values = public_values
            existing.encrypted_secrets = encrypted
            existing.updated_by_user_id = actor.id
            existing.updated_at = utc_now()
        record_audit(
            db,
            actor_user_id=actor.id,
            action="plugin.configuration.updated",
            resource_type="plugin",
            resource_id=plugin.id,
            details={"configured_properties": sorted(values), "secret_values_redacted": True},
        )
        emit_event(
            db,
            event_type="plugin.configuration.updated",
            resource_type="plugin",
            resource_id=plugin.id,
            payload={"configured_properties": sorted(values)},
        )
        return existing

    @staticmethod
    def list_plugins(db: Session, actor: User) -> list[PluginRecord]:
        return list(db.scalars(select(PluginRecord).order_by(PluginRecord.created_at.desc())))

    @staticmethod
    def list_plugins_page(
        db: Session,
        *,
        actor: User,
        limit: int,
        cursor: str | None,
        lifecycle_state: str | None,
        enabled: bool | None,
        query: str | None,
        sort: str,
        direction: str,
    ) -> PageResult[PluginRecord]:
        validate_page_sort(sort, PLUGIN_PAGE_SORTS)
        if lifecycle_state is not None:
            require(
                lifecycle_state in PLUGIN_LIFECYCLE_STATES,
                "Unsupported plugin lifecycle filter.",
            )
        normalized_query = query.strip().lower() if query else ""
        statement = select(PluginRecord)
        if lifecycle_state:
            statement = statement.where(PluginRecord.lifecycle_state == lifecycle_state)
        if enabled is not None:
            statement = statement.where(PluginRecord.enabled == enabled)
        if normalized_query:
            statement = statement.where(
                or_(
                    func.lower(PluginRecord.name).contains(normalized_query),
                    func.lower(PluginRecord.id).contains(normalized_query),
                )
            )
        return paginate(
            db,
            statement=statement,
            model=PluginRecord,
            resource="plugins",
            scope=repr((lifecycle_state, enabled, normalized_query)),
            sort=sort,
            direction=direction,
            limit=limit,
            cursor=cursor,
        )

    @staticmethod
    def get_plugin(db: Session, *, plugin_id: str, actor: User) -> PluginRecord:
        plugin = db.get(PluginRecord, plugin_id)
        if plugin is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found.")
        return plugin

    @staticmethod
    def set_plugin_enabled(
        db: Session,
        *,
        plugin_id: str,
        enabled: bool,
        actor: User,
    ) -> PluginRecord:
        PluginsModule.require_platform_admin(actor)
        plugin = db.get(PluginRecord, plugin_id)
        if plugin is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found.")
        if enabled:
            require(
                plugin.lifecycle_state in {"installed", "disabled", "failed", "running"},
                "Plugin must be installed and compatible before it can be enabled.",
                status.HTTP_409_CONFLICT,
            )
        plugin.enabled = enabled
        if enabled:
            plugin.lifecycle_state = "starting"
        elif plugin.lifecycle_state not in {"discovered", "incompatible"}:
            plugin.lifecycle_state = "disabled"
        plugin.diagnostic_reason = None
        plugin.updated_at = utc_now()
        record_audit(
            db,
            actor_user_id=actor.id,
            action="plugin.state.updated",
            resource_type="plugin",
            resource_id=plugin.id,
            details={"enabled": enabled, "lifecycle_state": plugin.lifecycle_state},
        )
        emit_event(
            db,
            event_type="plugin.state.updated",
            resource_type="plugin",
            resource_id=plugin.id,
            payload={"enabled": enabled, "lifecycle_state": plugin.lifecycle_state},
        )
        return plugin

    @staticmethod
    def record_runtime_state(
        db: Session,
        *,
        plugin_id: str,
        lifecycle_state: str,
        diagnostic_reason: str | None,
    ) -> PluginRecord:
        require(lifecycle_state in PLUGIN_LIFECYCLE_STATES, "Invalid plugin lifecycle state.")
        plugin = db.get(PluginRecord, plugin_id)
        if plugin is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found.")
        plugin.lifecycle_state = lifecycle_state
        plugin.enabled = lifecycle_state in {"starting", "running"}
        plugin.diagnostic_reason = diagnostic_reason[:1024] if diagnostic_reason else None
        plugin.updated_at = utc_now()
        record_audit(
            db,
            actor_user_id=None,
            action="plugin.runtime_state.updated",
            resource_type="plugin",
            resource_id=plugin.id,
            details={
                "lifecycle_state": lifecycle_state,
                "diagnostic_reason": plugin.diagnostic_reason,
            },
        )
        emit_event(
            db,
            event_type="plugin.runtime_state.updated",
            resource_type="plugin",
            resource_id=plugin.id,
            payload={"lifecycle_state": lifecycle_state},
        )
        return plugin

    @staticmethod
    def list_due_event_deliveries(
        db: Session, *, limit: int = 100
    ) -> list[PluginEventDeliveryView]:
        deliveries = db.scalars(
            select(PluginEventDelivery)
            .where(
                and_(
                    PluginEventDelivery.status.in_({"pending", "retry"}),
                    PluginEventDelivery.next_attempt_at <= utc_now(),
                    PluginEventDelivery.attempt_count < 3,
                )
            )
            .order_by(PluginEventDelivery.plugin_id, PluginEventDelivery.created_at)
            .limit(min(max(limit, 1), 100))
        )
        return [
            PluginEventDeliveryView(
                id=delivery.id,
                plugin_id=delivery.plugin_id,
                package_digest=delivery.plugin.package_digest,
                event_type=delivery.event_type,
                payload=delivery.payload,
                attempt_count=delivery.attempt_count,
            )
            for delivery in deliveries
        ]

    @staticmethod
    def list_event_deliveries(
        db: Session, *, plugin_id: str, actor: User
    ) -> list[PluginEventDelivery]:
        PluginsModule.require_platform_admin(actor)
        PluginsModule.get_plugin(db, plugin_id=plugin_id, actor=actor)
        return list(
            db.scalars(
                select(PluginEventDelivery)
                .where(PluginEventDelivery.plugin_id == plugin_id)
                .order_by(PluginEventDelivery.created_at.desc())
                .limit(100)
            )
        )

    @staticmethod
    def record_event_delivery_result(
        db: Session,
        *,
        delivery_id: str,
        success: bool,
        diagnostic_reason: str | None,
    ) -> PluginEventDelivery:
        delivery = db.get(PluginEventDelivery, delivery_id)
        if delivery is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Plugin event delivery not found."
            )
        delivery.attempt_count += 1
        delivery.updated_at = utc_now()
        if success:
            delivery.status = "delivered"
            delivery.last_error = None
        else:
            delivery.last_error = (
                diagnostic_reason[:1024] if diagnostic_reason else "Delivery failed."
            )
            if delivery.attempt_count >= 3:
                delivery.status = "failed"
            else:
                delivery.status = "retry"
                delivery.next_attempt_at = utc_now() + timedelta(
                    seconds=2 ** (delivery.attempt_count - 1)
                )
        record_audit(
            db,
            actor_user_id=None,
            action=f"plugin.event_delivery.{delivery.status}",
            resource_type="plugin",
            resource_id=delivery.plugin_id,
            details={
                "delivery_id": delivery.id,
                "event_type": delivery.event_type,
                "attempt_count": delivery.attempt_count,
                "diagnostic_reason": delivery.last_error,
            },
        )
        return delivery


@dataclass(slots=True)
class SessionContext:
    """Authenticated request context."""

    session_token: SessionToken
    user: User


@dataclass(slots=True)
class CollaborationState:
    """Resolved collaboration state for an Asset."""

    asset: Asset
    state: str
    lock: AssetCollaborationLock | None
    project_role: str | None
    can_checkin: bool
    can_unlock: bool
    can_force_unlock: bool


@dataclass(slots=True)
class TimelineEntry:
    """User-facing collaboration timeline entry."""

    event_type: str
    occurred_at: datetime
    actor_user_id: str | None
    asset_id: str
    revision_id: str | None
    details: dict[str, object]


@dataclass(slots=True)
class GraphQueryResult:
    """Bounded Phase 3 graph query result."""

    root_asset: Asset
    direction: str
    max_depth: int
    target_asset_id: str | None
    path_exists: bool | None
    has_cycle: bool
    nodes: list[Asset]
    relationships: list[AssetRelationship]
