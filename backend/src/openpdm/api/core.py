"""Phase 1 Core Platform API endpoints."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, cast

from fastapi import APIRouter, Depends, FastAPI, File, Header, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from openpdm import __version__
from openpdm.infrastructure.blob_storage import BlobStorage, build_blob_storage
from openpdm.infrastructure.database import get_db_session, initialize_database
from openpdm.platform_core.composition import MODULES
from openpdm.platform_core.public import (
    CollaborationStateView,
    GraphQueryResultView,
    SessionContextView,
    TimelineEntryView,
)

ALLOWED_STATUSES = {"draft", "active", "archived"}
CollaborationState = CollaborationStateView
GraphQueryResult = GraphQueryResultView
SessionContext = SessionContextView
TimelineEntry = TimelineEntryView

AuthModule = MODULES.authentication
OrganizationModule = MODULES.organizations
ProjectModule = MODULES.projects
BlobModule = MODULES.blobs
AssetsModule = MODULES.assets
RelationshipsModule = MODULES.relationships
CollaborationModule = MODULES.collaboration
MetadataModule = MODULES.metadata
SearchModule = MODULES.search
PluginsModule = MODULES.plugins
NotificationsModule = MODULES.notifications

router = APIRouter(tags=["Core Platform"])


class ApiModel(BaseModel):
    """Base response model."""

    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    status: str


class FoundationResponse(BaseModel):
    name: str
    version: str
    phase: str
    architecture: str


class UserResponse(ApiModel):
    id: str
    email: str
    display_name: str
    is_active: bool
    created_at: str


class SessionResponse(BaseModel):
    id: str
    token: str
    user: UserResponse


class OrganizationResponse(ApiModel):
    id: str
    name: str
    slug: str
    created_at: str


class OrganizationMembershipResponse(BaseModel):
    id: str
    role: str
    organization: OrganizationResponse | None = None
    user: UserResponse | None = None


class ProjectResponse(ApiModel):
    id: str
    organization_id: str
    name: str
    description: str
    created_at: str


class ProjectMembershipResponse(BaseModel):
    id: str
    role: str
    project: ProjectResponse | None = None
    user: UserResponse | None = None


class BlobResponse(ApiModel):
    id: str
    storage_key: str
    filename: str
    media_type: str
    size_bytes: int
    checksum_sha256: str
    created_at: str


class RepresentationResponse(ApiModel):
    id: str
    revision_id: str
    name: str
    media_type: str
    blob_id: str | None
    created_at: str
    blob: BlobResponse | None = None


class RevisionResponse(ApiModel):
    id: str
    asset_id: str
    number: int
    comment: str
    created_by_user_id: str
    created_at: str
    representations: list[RepresentationResponse] = Field(default_factory=list)


class AssetResponse(ApiModel):
    id: str
    project_id: str
    name: str
    description: str
    status: str
    created_by_user_id: str
    created_at: str
    updated_at: str
    revisions: list[RevisionResponse] = Field(default_factory=list)


class MetadataResponse(ApiModel):
    id: str
    asset_id: str | None
    revision_id: str | None
    representation_id: str | None
    key: str
    value: Any
    value_type: str
    source: str
    created_at: str


class RelationshipResponse(ApiModel):
    id: str
    source_asset_id: str
    target_asset_id: str
    relationship_type: str
    direction: str
    metadata: dict[str, Any]
    created_by_user_id: str
    created_at: str


class ReferenceResponse(ApiModel):
    id: str
    source_asset_id: str
    reference_type: str
    target_uri: str
    label: str
    metadata: dict[str, Any]
    created_by_user_id: str
    created_at: str


class GraphNodeResponse(BaseModel):
    id: str
    project_id: str
    name: str
    status: str


class GraphResponse(BaseModel):
    asset_id: str
    direction: str
    max_depth: int
    target_asset_id: str | None
    path_exists: bool | None
    has_cycle: bool
    nodes: list[GraphNodeResponse]
    relationships: list[RelationshipResponse]


class CollaborationLockResponse(BaseModel):
    id: str
    asset_id: str
    owner_user_id: str
    created_at: str


class CollaborationStateResponse(BaseModel):
    asset_id: str
    state: str
    can_checkin: bool
    can_unlock: bool
    can_force_unlock: bool
    lock: CollaborationLockResponse | None = None


class TimelineEntryResponse(BaseModel):
    event_type: str
    occurred_at: str
    actor_user_id: str | None
    asset_id: str
    revision_id: str | None
    details: dict[str, Any]


class PluginResponse(BaseModel):
    id: str
    name: str
    version: str
    type: str = Field(alias="plugin_type")
    capabilities: list[str]
    enabled: bool
    created_at: str

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class NotificationResponse(BaseModel):
    id: str
    recipient_user_id: str
    actor_user_id: str | None
    organization_id: str | None
    project_id: str
    asset_id: str | None
    revision_id: str | None
    event_type: str
    is_read: bool
    read_at: str | None
    details: dict[str, Any]
    created_at: str


class RegisterUserRequest(BaseModel):
    email: str
    display_name: str
    password: str


class SignInRequest(BaseModel):
    email: str
    password: str


class CreateOrganizationRequest(BaseModel):
    name: str
    slug: str


class AddOrganizationMemberRequest(BaseModel):
    user_id: str | None = None
    user_email: str | None = None
    role: str


class CreateProjectRequest(BaseModel):
    organization_id: str
    name: str
    description: str = ""


class AddProjectMemberRequest(BaseModel):
    user_id: str | None = None
    user_email: str | None = None
    role: str


class ChangeMembershipRoleRequest(BaseModel):
    role: str


class CreateAssetRequest(BaseModel):
    name: str
    description: str = ""


class CreateRevisionRequest(BaseModel):
    comment: str = ""


class CreateRepresentationRequest(BaseModel):
    name: str
    media_type: str
    blob_id: str | None = None


class CollaborationRepresentationRequest(BaseModel):
    name: str
    media_type: str
    blob_id: str | None = None


class CheckInRequest(BaseModel):
    comment: str
    representations: list[CollaborationRepresentationRequest] = Field(default_factory=list)


class UnlockRequest(BaseModel):
    force: bool = False


class UpdateStatusRequest(BaseModel):
    status: str


class PutMetadataRequest(BaseModel):
    key: str
    value: Any
    value_type: str
    source: str = "user"


class CreateRelationshipRequest(BaseModel):
    target_asset_id: str
    relationship_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateRelationshipMetadataRequest(BaseModel):
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateReferenceRequest(BaseModel):
    reference_type: str
    target_uri: str
    label: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResolveReferenceRequest(BaseModel):
    target_asset_id: str
    relationship_type: str


class RegisterPluginRequest(BaseModel):
    id: str
    name: str
    version: str
    type: str
    capabilities: list[str] = Field(default_factory=list)


class SetPluginStateRequest(BaseModel):
    enabled: bool


def _iso(value: object) -> str:
    return cast(datetime, value).isoformat()


def serialize_user(user: Any) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
        created_at=_iso(user.created_at),
    )


def serialize_organization(organization: Any) -> OrganizationResponse:
    return OrganizationResponse(
        id=organization.id,
        name=organization.name,
        slug=organization.slug,
        created_at=_iso(organization.created_at),
    )


def serialize_project(project: Any) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        organization_id=project.organization_id,
        name=project.name,
        description=project.description,
        created_at=_iso(project.created_at),
    )


def serialize_blob(blob: Any) -> BlobResponse:
    return BlobResponse(
        id=blob.id,
        storage_key=blob.storage_key,
        filename=blob.filename,
        media_type=blob.media_type,
        size_bytes=blob.size_bytes,
        checksum_sha256=blob.checksum_sha256,
        created_at=_iso(blob.created_at),
    )


def serialize_representation(representation: Any) -> RepresentationResponse:
    return RepresentationResponse(
        id=representation.id,
        revision_id=representation.revision_id,
        name=representation.name,
        media_type=representation.media_type,
        blob_id=representation.blob_id,
        created_at=_iso(representation.created_at),
        blob=serialize_blob(representation.blob) if representation.blob is not None else None,
    )


def serialize_revision(revision: Any) -> RevisionResponse:
    return RevisionResponse(
        id=revision.id,
        asset_id=revision.asset_id,
        number=revision.number,
        comment=revision.comment,
        created_by_user_id=revision.created_by_user_id,
        created_at=_iso(revision.created_at),
        representations=[serialize_representation(item) for item in revision.representations],
    )


def serialize_asset(asset: Any) -> AssetResponse:
    ordered_revisions = sorted(asset.revisions, key=lambda item: item.number)
    return AssetResponse(
        id=asset.id,
        project_id=asset.project_id,
        name=asset.name,
        description=asset.description,
        status=asset.status,
        created_by_user_id=asset.created_by_user_id,
        created_at=_iso(asset.created_at),
        updated_at=_iso(asset.updated_at),
        revisions=[serialize_revision(item) for item in ordered_revisions],
    )


def serialize_metadata(entry: Any) -> MetadataResponse:
    return MetadataResponse(
        id=entry.id,
        asset_id=entry.asset_id,
        revision_id=entry.revision_id,
        representation_id=entry.representation_id,
        key=entry.key,
        value=entry.value,
        value_type=entry.value_type,
        source=entry.source,
        created_at=_iso(entry.created_at),
    )


def serialize_relationship(relationship: Any) -> RelationshipResponse:
    return RelationshipResponse(
        id=relationship.id,
        source_asset_id=relationship.source_asset_id,
        target_asset_id=relationship.target_asset_id,
        relationship_type=relationship.relationship_type,
        direction=relationship.direction,
        metadata=relationship.metadata_json,
        created_by_user_id=relationship.created_by_user_id,
        created_at=_iso(relationship.created_at),
    )


def serialize_reference(reference: Any) -> ReferenceResponse:
    return ReferenceResponse(
        id=reference.id,
        source_asset_id=reference.source_asset_id,
        reference_type=reference.reference_type,
        target_uri=reference.target_uri,
        label=reference.label,
        metadata=reference.metadata_json,
        created_by_user_id=reference.created_by_user_id,
        created_at=_iso(reference.created_at),
    )


def serialize_graph(result: GraphQueryResult) -> GraphResponse:
    ordered_nodes = sorted(result.nodes, key=lambda item: item.name.lower())
    ordered_relationships = sorted(
        result.relationships,
        key=lambda item: (
            item.source_asset_id,
            item.target_asset_id,
            item.relationship_type,
            item.created_at,
        ),
    )
    return GraphResponse(
        asset_id=result.root_asset.id,
        direction=result.direction,
        max_depth=result.max_depth,
        target_asset_id=result.target_asset_id,
        path_exists=result.path_exists,
        has_cycle=result.has_cycle,
        nodes=[
            GraphNodeResponse(
                id=node.id,
                project_id=node.project_id,
                name=node.name,
                status=node.status,
            )
            for node in ordered_nodes
        ],
        relationships=[serialize_relationship(item) for item in ordered_relationships],
    )


def serialize_collaboration_state(state: CollaborationState) -> CollaborationStateResponse:
    lock = state.lock
    return CollaborationStateResponse(
        asset_id=state.asset.id,
        state=state.state,
        can_checkin=state.can_checkin,
        can_unlock=state.can_unlock,
        can_force_unlock=state.can_force_unlock,
        lock=(
            CollaborationLockResponse(
                id=lock.id,
                asset_id=lock.asset_id,
                owner_user_id=lock.owner_user_id,
                created_at=_iso(lock.created_at),
            )
            if lock is not None
            else None
        ),
    )


def serialize_timeline_entry(entry: TimelineEntry) -> TimelineEntryResponse:
    return TimelineEntryResponse(
        event_type=entry.event_type,
        occurred_at=_iso(entry.occurred_at),
        actor_user_id=entry.actor_user_id,
        asset_id=entry.asset_id,
        revision_id=entry.revision_id,
        details=entry.details,
    )


def serialize_plugin(plugin: Any) -> PluginResponse:
    return PluginResponse(
        id=plugin.id,
        name=plugin.name,
        version=plugin.version,
        type=plugin.plugin_type,
        capabilities=plugin.capabilities,
        enabled=plugin.enabled,
        created_at=_iso(plugin.created_at),
    )


def serialize_notification(notification: Any) -> NotificationResponse:
    return NotificationResponse(
        id=notification.id,
        recipient_user_id=notification.recipient_user_id,
        actor_user_id=notification.actor_user_id,
        organization_id=notification.organization_id,
        project_id=notification.project_id,
        asset_id=notification.asset_id,
        revision_id=notification.revision_id,
        event_type=notification.event_type,
        is_read=notification.is_read,
        read_at=_iso(notification.read_at) if notification.read_at is not None else None,
        details=notification.details,
        created_at=_iso(notification.created_at),
    )


def get_storage() -> BlobStorage:
    """FastAPI dependency for blob storage."""
    return build_blob_storage()


def extract_bearer_token(authorization: str | None) -> str:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token is required.",
        )
    return authorization.removeprefix("Bearer ").strip()


def get_authenticated_session(
    db: Session = Depends(get_db_session),
    authorization: str | None = Header(default=None),
) -> SessionContext:
    token = extract_bearer_token(authorization)
    session_token = AuthModule.get_session(db, token)
    return SessionContext(session_token=session_token, user=session_token.user)


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/foundation", response_model=FoundationResponse)
def foundation() -> FoundationResponse:
    return FoundationResponse(
        name="OpenPDM",
        version=__version__,
        phase="Core Platform",
        architecture="Modular Monolith",
    )


@router.post(
    "/auth/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    payload: RegisterUserRequest,
    db: Session = Depends(get_db_session),
) -> UserResponse:
    user = AuthModule.register_user(
        db, email=payload.email, display_name=payload.display_name, password=payload.password
    )
    db.commit()
    db.refresh(user)
    return serialize_user(user)


@router.post("/auth/sign-in", response_model=SessionResponse)
def sign_in(
    payload: SignInRequest,
    db: Session = Depends(get_db_session),
) -> SessionResponse:
    user, session_token = AuthModule.sign_in(db, email=payload.email, password=payload.password)
    db.commit()
    db.refresh(session_token)
    return SessionResponse(
        id=session_token.id,
        token=session_token.token,
        user=serialize_user(user),
    )


@router.get("/auth/session", response_model=SessionResponse)
def get_current_session(
    context: SessionContext = Depends(get_authenticated_session),
) -> SessionResponse:
    return SessionResponse(
        id=context.session_token.id,
        token=context.session_token.token,
        user=serialize_user(context.user),
    )


@router.post("/auth/sign-out", response_model=SessionResponse)
def sign_out(
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> SessionResponse:
    revoked = AuthModule.revoke_session(
        db,
        session_token=context.session_token,
        actor_user_id=context.user.id,
    )
    db.commit()
    return SessionResponse(
        id=revoked.id,
        token=revoked.token,
        user=serialize_user(context.user),
    )


@router.post("/auth/sessions/{session_id}/revoke", response_model=SessionResponse)
def revoke_session_by_id(
    session_id: str,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> SessionResponse:
    target = AuthModule.get_session_by_id(db, session_id=session_id)
    revoked = AuthModule.revoke_session(
        db,
        session_token=target,
        actor_user_id=context.user.id,
    )
    db.commit()
    return SessionResponse(
        id=revoked.id,
        token=revoked.token,
        user=serialize_user(context.user),
    )


@router.post(
    "/organizations", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED
)
def create_organization(
    payload: CreateOrganizationRequest,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> OrganizationResponse:
    organization = OrganizationModule.create_organization(
        db, actor=context.user, name=payload.name, slug=payload.slug
    )
    db.commit()
    return serialize_organization(organization)


@router.get("/organizations", response_model=list[OrganizationMembershipResponse])
def list_organizations(
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> list[OrganizationMembershipResponse]:
    memberships = OrganizationModule.list_user_organizations(db, actor=context.user)
    return [
        OrganizationMembershipResponse(
            id=item.id,
            role=item.role,
            organization=serialize_organization(item.organization),
        )
        for item in memberships
    ]


@router.get("/organizations/{organization_id}", response_model=OrganizationResponse)
def get_organization(
    organization_id: str,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> OrganizationResponse:
    organization = OrganizationModule.get_organization(db, organization_id, context.user)
    return serialize_organization(organization)


@router.post(
    "/organizations/{organization_id}/members", response_model=OrganizationMembershipResponse
)
def add_organization_member(
    organization_id: str,
    payload: AddOrganizationMemberRequest,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> OrganizationMembershipResponse:
    OrganizationModule.require_membership_management(
        db, organization_id=organization_id, actor=context.user
    )
    target_user = OrganizationModule.resolve_registered_user(
        db, user_id=payload.user_id, user_email=payload.user_email
    )
    membership = OrganizationModule.add_member(
        db,
        organization_id=organization_id,
        user_id=target_user.id,
        role=payload.role,
        actor=context.user,
    )
    db.commit()
    db.refresh(membership)
    return OrganizationMembershipResponse(
        id=membership.id, role=membership.role, user=serialize_user(target_user)
    )


@router.patch(
    "/organizations/{organization_id}/members/{membership_id}",
    response_model=OrganizationMembershipResponse,
)
def change_organization_member_role(
    organization_id: str,
    membership_id: str,
    payload: ChangeMembershipRoleRequest,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> OrganizationMembershipResponse:
    membership = OrganizationModule.change_member_role(
        db,
        organization_id=organization_id,
        membership_id=membership_id,
        role=payload.role,
        actor=context.user,
    )
    db.commit()
    return OrganizationMembershipResponse(
        id=membership.id, role=membership.role, user=serialize_user(membership.user)
    )


@router.delete(
    "/organizations/{organization_id}/members/{membership_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_organization_member(
    organization_id: str,
    membership_id: str,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> Response:
    OrganizationModule.require_membership_management(
        db, organization_id=organization_id, actor=context.user
    )
    membership = OrganizationModule.get_membership(
        db, organization_id=organization_id, membership_id=membership_id
    )
    ProjectModule.remove_user_memberships_for_organization(
        db, organization_id=organization_id, user_id=membership.user_id, actor=context.user
    )
    OrganizationModule.remove_member(
        db,
        organization_id=organization_id,
        membership_id=membership_id,
        actor=context.user,
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/organizations/{organization_id}/members", response_model=list[OrganizationMembershipResponse]
)
def list_organization_members(
    organization_id: str,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> list[OrganizationMembershipResponse]:
    memberships = OrganizationModule.list_members(
        db,
        organization_id=organization_id,
        actor=context.user,
    )
    return [
        OrganizationMembershipResponse(id=item.id, role=item.role, user=serialize_user(item.user))
        for item in memberships
    ]


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: CreateProjectRequest,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> ProjectResponse:
    project = ProjectModule.create_project(
        db,
        organization_id=payload.organization_id,
        name=payload.name,
        description=payload.description,
        actor=context.user,
    )
    db.commit()
    return serialize_project(project)


@router.get("/organizations/{organization_id}/projects", response_model=list[ProjectResponse])
def list_organization_projects(
    organization_id: str,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> list[ProjectResponse]:
    projects = ProjectModule.list_organization_projects(
        db,
        organization_id=organization_id,
        actor=context.user,
    )
    return [serialize_project(item) for item in projects]


@router.get(
    "/organizations/{organization_id}/projects/me", response_model=list[ProjectMembershipResponse]
)
def list_user_projects(
    organization_id: str,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> list[ProjectMembershipResponse]:
    return [
        ProjectMembershipResponse(
            id=item.id, role=item.role, project=serialize_project(item.project)
        )
        for item in ProjectModule.list_user_projects(
            db, organization_id=organization_id, actor=context.user
        )
    ]


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: str,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> ProjectResponse:
    return serialize_project(
        ProjectModule.get_project(db, project_id=project_id, actor=context.user)
    )


@router.post("/projects/{project_id}/members", response_model=ProjectMembershipResponse)
def add_project_member(
    project_id: str,
    payload: AddProjectMemberRequest,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> ProjectMembershipResponse:
    ProjectModule.require_project_permission(
        db, project_id=project_id, actor=context.user, permission="manage_members"
    )
    target_user = OrganizationModule.resolve_registered_user(
        db, user_id=payload.user_id, user_email=payload.user_email
    )
    membership = ProjectModule.add_member(
        db, project_id=project_id, user_id=target_user.id, role=payload.role, actor=context.user
    )
    db.commit()
    return ProjectMembershipResponse(
        id=membership.id, role=membership.role, user=serialize_user(target_user)
    )


@router.patch(
    "/projects/{project_id}/members/{membership_id}",
    response_model=ProjectMembershipResponse,
)
def change_project_member_role(
    project_id: str,
    membership_id: str,
    payload: ChangeMembershipRoleRequest,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> ProjectMembershipResponse:
    membership = ProjectModule.change_member_role(
        db,
        project_id=project_id,
        membership_id=membership_id,
        role=payload.role,
        actor=context.user,
    )
    db.commit()
    return ProjectMembershipResponse(
        id=membership.id, role=membership.role, user=serialize_user(membership.user)
    )


@router.delete(
    "/projects/{project_id}/members/{membership_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_project_member(
    project_id: str,
    membership_id: str,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> Response:
    ProjectModule.remove_member(
        db, project_id=project_id, membership_id=membership_id, actor=context.user
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/projects/{project_id}/members", response_model=list[ProjectMembershipResponse])
def list_project_members(
    project_id: str,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> list[ProjectMembershipResponse]:
    memberships = ProjectModule.list_members(db, project_id=project_id, actor=context.user)
    return [
        ProjectMembershipResponse(id=item.id, role=item.role, user=serialize_user(item.user))
        for item in memberships
    ]


@router.get("/notifications", response_model=list[NotificationResponse])
def list_notifications(
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> list[NotificationResponse]:
    return [
        serialize_notification(item)
        for item in NotificationsModule.list_notifications(db, actor=context.user)
    ]


@router.post("/notifications/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: str,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> NotificationResponse:
    notification = NotificationsModule.mark_read(
        db, notification_id=notification_id, actor=context.user
    )
    db.commit()
    return serialize_notification(notification)


@router.post("/blobs/uploads", response_model=BlobResponse, status_code=status.HTTP_201_CREATED)
async def upload_blob(
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
    storage: BlobStorage = Depends(get_storage),
    file: UploadFile = File(...),
) -> BlobResponse:
    blob = await BlobModule.upload_blob(db, actor=context.user, file=file, storage=storage)
    db.commit()
    return serialize_blob(blob)


@router.get("/blobs/{blob_id}/download")
def download_blob(
    blob_id: str,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
    storage: BlobStorage = Depends(get_storage),
) -> Response:
    blob, content = BlobModule.download_blob(
        db,
        blob_id=blob_id,
        actor=context.user,
        storage=storage,
    )
    return Response(
        content=content,
        media_type=blob.media_type,
        headers={"Content-Disposition": f'attachment; filename="{blob.filename}"'},
    )


@router.post(
    "/projects/{project_id}/assets",
    response_model=AssetResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_asset(
    project_id: str,
    payload: CreateAssetRequest,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> AssetResponse:
    asset = AssetsModule.create_asset(
        db,
        project_id=project_id,
        name=payload.name,
        description=payload.description,
        actor=context.user,
    )
    db.commit()
    return serialize_asset(asset)


@router.get("/projects/{project_id}/assets", response_model=list[AssetResponse])
def list_assets(
    project_id: str,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> list[AssetResponse]:
    return [
        serialize_asset(item)
        for item in AssetsModule.list_assets(db, project_id=project_id, actor=context.user)
    ]


@router.get("/assets/{asset_id}", response_model=AssetResponse)
def get_asset(
    asset_id: str,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> AssetResponse:
    return serialize_asset(AssetsModule.get_asset(db, asset_id=asset_id, actor=context.user))


@router.post(
    "/assets/{asset_id}/relationships",
    response_model=RelationshipResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_relationship(
    asset_id: str,
    payload: CreateRelationshipRequest,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> RelationshipResponse:
    relationship = RelationshipsModule.create_relationship(
        db,
        source_asset_id=asset_id,
        target_asset_id=payload.target_asset_id,
        relationship_type=payload.relationship_type,
        metadata=payload.metadata,
        actor=context.user,
    )
    db.commit()
    return serialize_relationship(relationship)


@router.get("/assets/{asset_id}/relationships", response_model=list[RelationshipResponse])
def list_relationships(
    asset_id: str,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> list[RelationshipResponse]:
    return [
        serialize_relationship(item)
        for item in RelationshipsModule.list_relationships(
            db, asset_id=asset_id, actor=context.user
        )
    ]


@router.get("/assets/{asset_id}/relationships/incoming", response_model=list[RelationshipResponse])
def list_incoming_relationships(
    asset_id: str,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> list[RelationshipResponse]:
    return [
        serialize_relationship(item)
        for item in RelationshipsModule.list_incoming_relationships(
            db, asset_id=asset_id, actor=context.user
        )
    ]


@router.get("/assets/{asset_id}/relationships/outgoing", response_model=list[RelationshipResponse])
def list_outgoing_relationships(
    asset_id: str,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> list[RelationshipResponse]:
    return [
        serialize_relationship(item)
        for item in RelationshipsModule.list_outgoing_relationships(
            db, asset_id=asset_id, actor=context.user
        )
    ]


@router.put("/relationships/{relationship_id}/metadata", response_model=RelationshipResponse)
def update_relationship_metadata(
    relationship_id: str,
    payload: UpdateRelationshipMetadataRequest,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> RelationshipResponse:
    relationship = RelationshipsModule.update_relationship_metadata(
        db,
        relationship_id=relationship_id,
        metadata=payload.metadata,
        actor=context.user,
    )
    db.commit()
    return serialize_relationship(relationship)


@router.delete("/relationships/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_relationship(
    relationship_id: str,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> Response:
    RelationshipsModule.delete_relationship(db, relationship_id=relationship_id, actor=context.user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/assets/{asset_id}/references",
    response_model=ReferenceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_reference(
    asset_id: str,
    payload: CreateReferenceRequest,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> ReferenceResponse:
    reference = RelationshipsModule.create_reference(
        db,
        source_asset_id=asset_id,
        reference_type=payload.reference_type,
        target_uri=payload.target_uri,
        label=payload.label,
        metadata=payload.metadata,
        actor=context.user,
    )
    db.commit()
    return serialize_reference(reference)


@router.get("/assets/{asset_id}/references", response_model=list[ReferenceResponse])
def list_references(
    asset_id: str,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> list[ReferenceResponse]:
    return [
        serialize_reference(item)
        for item in RelationshipsModule.list_references(db, asset_id=asset_id, actor=context.user)
    ]


@router.post("/references/{reference_id}/resolve", response_model=RelationshipResponse)
def resolve_reference(
    reference_id: str,
    payload: ResolveReferenceRequest,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> RelationshipResponse:
    relationship = RelationshipsModule.resolve_reference(
        db,
        reference_id=reference_id,
        target_asset_id=payload.target_asset_id,
        relationship_type=payload.relationship_type,
        actor=context.user,
    )
    db.commit()
    return serialize_relationship(relationship)


@router.delete("/references/{reference_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reference(
    reference_id: str,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> Response:
    RelationshipsModule.delete_reference(db, reference_id=reference_id, actor=context.user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/assets/{asset_id}/graph", response_model=GraphResponse)
def get_asset_graph(
    asset_id: str,
    direction: str = "outgoing",
    max_depth: int = 3,
    target_asset_id: str | None = None,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> GraphResponse:
    result = RelationshipsModule.get_graph(
        db,
        asset_id=asset_id,
        actor=context.user,
        direction=direction,
        max_depth=max_depth,
        target_asset_id=target_asset_id,
    )
    db.commit()
    return serialize_graph(result)


@router.get("/assets/{asset_id}/collaboration-state", response_model=CollaborationStateResponse)
def get_collaboration_state(
    asset_id: str,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> CollaborationStateResponse:
    state = CollaborationModule.get_collaboration_state(db, asset_id=asset_id, actor=context.user)
    return serialize_collaboration_state(state)


@router.post("/assets/{asset_id}/checkout", response_model=CollaborationStateResponse)
def checkout_asset(
    asset_id: str,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> CollaborationStateResponse:
    state = CollaborationModule.checkout(db, asset_id=asset_id, actor=context.user)
    db.commit()
    return serialize_collaboration_state(state)


@router.post("/assets/{asset_id}/unlock", response_model=CollaborationStateResponse)
def unlock_asset(
    asset_id: str,
    payload: UnlockRequest,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> CollaborationStateResponse:
    state = CollaborationModule.unlock(
        db, asset_id=asset_id, actor=context.user, force=payload.force
    )
    db.commit()
    return serialize_collaboration_state(state)


@router.get("/assets/{asset_id}/timeline", response_model=list[TimelineEntryResponse])
def get_asset_timeline(
    asset_id: str,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> list[TimelineEntryResponse]:
    return [
        serialize_timeline_entry(item)
        for item in CollaborationModule.list_timeline(db, asset_id=asset_id, actor=context.user)
    ]


@router.get("/assets/{asset_id}/history", response_model=list[RevisionResponse])
def get_asset_history(
    asset_id: str,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> list[RevisionResponse]:
    return [
        serialize_revision(item)
        for item in AssetsModule.list_history(db, asset_id=asset_id, actor=context.user)
    ]


@router.post(
    "/assets/{asset_id}/revisions",
    response_model=RevisionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_revision(
    asset_id: str,
    payload: CreateRevisionRequest,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> RevisionResponse:
    revision = AssetsModule.create_revision(
        db, asset_id=asset_id, comment=payload.comment, actor=context.user
    )
    db.commit()
    return serialize_revision(revision)


@router.post(
    "/assets/{asset_id}/checkin",
    response_model=RevisionResponse,
    status_code=status.HTTP_201_CREATED,
)
def checkin_asset(
    asset_id: str,
    payload: CheckInRequest,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> RevisionResponse:
    revision = CollaborationModule.checkin(
        db,
        asset_id=asset_id,
        comment=payload.comment,
        representations=[item.model_dump() for item in payload.representations],
        actor=context.user,
    )
    db.commit()
    return serialize_revision(revision)


@router.post(
    "/revisions/{revision_id}/representations",
    response_model=RepresentationResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_representation(
    revision_id: str,
    payload: CreateRepresentationRequest,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> RepresentationResponse:
    representation = AssetsModule.add_representation(
        db,
        revision_id=revision_id,
        name=payload.name,
        media_type=payload.media_type,
        blob_id=payload.blob_id,
        actor=context.user,
    )
    db.commit()
    return serialize_representation(representation)


@router.post("/assets/{asset_id}/status", response_model=AssetResponse)
def update_asset_status(
    asset_id: str,
    payload: UpdateStatusRequest,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> AssetResponse:
    if payload.status not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid lifecycle status."
        )
    asset = AssetsModule.update_status(
        db, asset_id=asset_id, status_value=payload.status, actor=context.user
    )
    db.commit()
    return serialize_asset(asset)


@router.put("/metadata/{target_type}/{target_id}", response_model=MetadataResponse)
def put_metadata(
    target_type: str,
    target_id: str,
    payload: PutMetadataRequest,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> MetadataResponse:
    entry = MetadataModule.put_entry(
        db,
        target_type=target_type,
        target_id=target_id,
        key=payload.key,
        value=payload.value,
        value_type=payload.value_type,
        source=payload.source,
        actor=context.user,
    )
    db.commit()
    return serialize_metadata(entry)


@router.get("/metadata/{target_type}/{target_id}", response_model=list[MetadataResponse])
def list_metadata(
    target_type: str,
    target_id: str,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> list[MetadataResponse]:
    return [
        serialize_metadata(item)
        for item in MetadataModule.list_entries(
            db, target_type=target_type, target_id=target_id, actor=context.user
        )
    ]


@router.get("/search/assets", response_model=list[AssetResponse])
def search_assets(
    q: str,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
    organization_id: str | None = None,
    project_id: str | None = None,
) -> list[AssetResponse]:
    return [
        serialize_asset(item)
        for item in SearchModule.search_assets(
            db,
            query_text=q,
            actor=context.user,
            organization_id=organization_id,
            project_id=project_id,
        )
    ]


@router.post("/plugins", response_model=PluginResponse, status_code=status.HTTP_201_CREATED)
def register_plugin(
    payload: RegisterPluginRequest,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> PluginResponse:
    plugin = PluginsModule.register_plugin(
        db,
        plugin_id=payload.id,
        name=payload.name,
        version=payload.version,
        plugin_type=payload.type,
        capabilities=payload.capabilities,
        actor=context.user,
    )
    db.commit()
    return serialize_plugin(plugin)


@router.get("/plugins", response_model=list[PluginResponse])
def list_plugins(
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> list[PluginResponse]:
    return [serialize_plugin(item) for item in PluginsModule.list_plugins(db, actor=context.user)]


@router.post("/plugins/{plugin_id}/state", response_model=PluginResponse)
def set_plugin_state(
    plugin_id: str,
    payload: SetPluginStateRequest,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> PluginResponse:
    plugin = PluginsModule.set_plugin_enabled(
        db, plugin_id=plugin_id, enabled=payload.enabled, actor=context.user
    )
    db.commit()
    return serialize_plugin(plugin)


@asynccontextmanager
async def application_lifespan(app: FastAPI) -> Generator[None, None, None]:
    initialize_database()
    build_blob_storage()
    yield
