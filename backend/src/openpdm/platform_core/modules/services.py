"""Platform Module public services for the Phase 1 Core Platform MVP."""

from __future__ import annotations

import base64
import hashlib
import secrets
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import String, and_, cast, func, literal, or_, select
from sqlalchemy.orm import Session, joinedload

from openpdm.infrastructure.blob_storage import BlobStorage
from openpdm.platform_core.modules.models import (
    Asset,
    AssetCollaborationLock,
    AuditRecord,
    Blob,
    DomainEvent,
    MetadataEntry,
    NotificationRecord,
    Organization,
    OrganizationMembership,
    PluginRecord,
    Project,
    ProjectMembership,
    Representation,
    Revision,
    SessionToken,
    User,
)

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
ALLOWED_METADATA_TYPES = {"string", "number", "boolean", "date", "json"}
ALLOWED_PLUGIN_TYPES = {"official", "community"}
COLLABORATION_STATES = {"available", "locked", "stale_lock"}
FORCE_UNLOCK_ROLES = {"Owner", "Maintainer"}
LOCK_OWNER_WRITE_ROLES = {"Owner", "Maintainer", "Contributor"}
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
CURRENT_REQUEST_ID: ContextVar[str | None] = ContextVar("openpdm_request_id", default=None)


def utc_now() -> datetime:
    """Return the current UTC time."""
    return datetime.now(UTC)


def set_request_id(value: str | None) -> object:
    """Set the current request identifier for observability helpers."""
    return CURRENT_REQUEST_ID.set(value)


def reset_request_id(token: object) -> None:
    """Restore the previous request identifier after a request completes."""
    CURRENT_REQUEST_ID.reset(token)


def get_request_id() -> str | None:
    """Return the active request identifier if one is available."""
    return CURRENT_REQUEST_ID.get()


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
    db.add(
        DomainEvent(
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            organization_id=organization_id,
            project_id=project_id,
            payload=event_payload,
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
        user = User(
            email=email.lower().strip(),
            display_name=display_name.strip(),
            password_hash=hash_password(password),
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
        actor_role = _membership_role(
            db,
            model=OrganizationMembership,
            field_name="organization_id",
            parent_id=organization_id,
            user_id=actor.id,
        )
        require(
            actor_role in {"Owner", "Maintainer"},
            "Organization membership cannot be managed.",
            status.HTTP_403_FORBIDDEN,
        )
        require(role in ORG_ROLE_PRIORITY, "Invalid Organization role.")
        get_user_or_404(db, user_id)
        OrganizationModule.get_organization(db, organization_id, actor)
        membership = db.scalar(
            select(OrganizationMembership).where(
                and_(
                    OrganizationMembership.organization_id == organization_id,
                    OrganizationMembership.user_id == user_id,
                )
            )
        )
        if membership is None:
            membership = OrganizationMembership(
                organization_id=organization_id, user_id=user_id, role=role
            )
            db.add(membership)
        else:
            membership.role = role
        db.flush()
        record_audit(
            db,
            actor_user_id=actor.id,
            action="organization.membership.upserted",
            resource_type="organization_membership",
            resource_id=membership.id,
            organization_id=organization_id,
            details={"target_user_id": user_id, "role": role},
        )
        emit_event(
            db,
            event_type="organization.membership.upserted",
            resource_type="organization_membership",
            resource_id=membership.id,
            organization_id=organization_id,
            payload={"target_user_id": user_id, "role": role},
        )
        return membership

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
        org_role = _membership_role(
            db,
            model=OrganizationMembership,
            field_name="organization_id",
            parent_id=project.organization_id,
            user_id=user_id,
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
        if membership is None:
            membership = ProjectMembership(project_id=project_id, user_id=user_id, role=role)
            db.add(membership)
        else:
            membership.role = role
        db.flush()
        record_audit(
            db,
            actor_user_id=actor.id,
            action="project.membership.upserted",
            resource_type="project_membership",
            resource_id=membership.id,
            organization_id=project.organization_id,
            project_id=project.id,
            details={"target_user_id": user_id, "role": role},
        )
        emit_event(
            db,
            event_type="project.membership.upserted",
            resource_type="project_membership",
            resource_id=membership.id,
            organization_id=project.organization_id,
            project_id=project.id,
            payload={"target_user_id": user_id, "role": role},
        )
        return membership

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
            if actor_user_id is not None and not include_actor and recipient_user_id == actor_user_id:
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
        visible_project_ids = NotificationsModule._visible_project_ids_for_user(db, user_id=actor.id)
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
        visible_project_ids = NotificationsModule._visible_project_ids_for_user(db, user_id=actor.id)
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
        storage_key = f"{utc_now().strftime('%Y/%m/%d')}/{secrets.token_hex(16)}-{file.filename}"
        storage.put_bytes(storage_key, content, file.content_type)
        blob = Blob(
            storage_key=storage_key,
            filename=file.filename or "blob.bin",
            media_type=file.content_type or "application/octet-stream",
            size_bytes=len(content),
            checksum_sha256=checksum,
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
    def download_blob(db: Session, *, blob_id: str, storage: BlobStorage) -> tuple[Blob, bytes]:
        blob = db.get(Blob, blob_id)
        if blob is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blob not found.")
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
                joinedload(Asset.revisions).joinedload(Revision.representations).joinedload(
                    Representation.blob
                ),
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
    def get_collaboration_state(
        db: Session, *, asset_id: str, actor: User
    ) -> CollaborationState:
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
        raise collaboration_error(code=code, message=message, status_code=status_code, context=payload)

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
        raise collaboration_error(code=code, message=message, status_code=status_code, context=payload)

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
        return db.scalar(
            select(Revision)
            .options(joinedload(Revision.representations).joinedload(Representation.blob))
            .where(Revision.id == revision.id)
        ) or revision

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
    """Public Plugins module service."""

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
        require(plugin_type in ALLOWED_PLUGIN_TYPES, "Invalid plugin type.")
        existing = db.get(PluginRecord, plugin_id)
        require(existing is None, "Plugin already exists.", status.HTTP_409_CONFLICT)
        plugin = PluginRecord(
            id=plugin_id.strip(),
            name=name.strip(),
            version=version.strip(),
            plugin_type=plugin_type,
            capabilities=capabilities,
            enabled=True,
        )
        db.add(plugin)
        db.flush()
        record_audit(
            db,
            actor_user_id=actor.id,
            action="plugin.registered",
            resource_type="plugin",
            resource_id=plugin.id,
        )
        emit_event(
            db,
            event_type="plugin.registered",
            resource_type="plugin",
            resource_id=plugin.id,
        )
        return plugin

    @staticmethod
    def list_plugins(db: Session, actor: User) -> list[PluginRecord]:
        return list(db.scalars(select(PluginRecord).order_by(PluginRecord.created_at.desc())))

    @staticmethod
    def set_plugin_enabled(
        db: Session,
        *,
        plugin_id: str,
        enabled: bool,
        actor: User,
    ) -> PluginRecord:
        plugin = db.get(PluginRecord, plugin_id)
        if plugin is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found.")
        plugin.enabled = enabled
        record_audit(
            db,
            actor_user_id=actor.id,
            action="plugin.state.updated",
            resource_type="plugin",
            resource_id=plugin.id,
            details={"enabled": enabled},
        )
        emit_event(
            db,
            event_type="plugin.state.updated",
            resource_type="plugin",
            resource_id=plugin.id,
            payload={"enabled": enabled},
        )
        return plugin


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
