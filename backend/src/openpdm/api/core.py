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
from openpdm.platform_core.modules.models import (
    Asset,
    MetadataEntry,
    PluginRecord,
    Representation,
    Revision,
    SessionToken,
)
from openpdm.platform_core.modules.services import (
    ALLOWED_STATUSES,
    AssetsModule,
    AuthModule,
    BlobModule,
    MetadataModule,
    OrganizationModule,
    PluginsModule,
    ProjectModule,
    SearchModule,
    SessionContext,
)

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


class PluginResponse(BaseModel):
    id: str
    name: str
    version: str
    type: str = Field(alias="plugin_type")
    capabilities: list[str]
    enabled: bool
    created_at: str

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


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
    user_id: str
    role: str


class CreateProjectRequest(BaseModel):
    organization_id: str
    name: str
    description: str = ""


class AddProjectMemberRequest(BaseModel):
    user_id: str
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


class UpdateStatusRequest(BaseModel):
    status: str


class PutMetadataRequest(BaseModel):
    key: str
    value: Any
    value_type: str
    source: str = "user"


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


def serialize_representation(representation: Representation) -> RepresentationResponse:
    return RepresentationResponse(
        id=representation.id,
        revision_id=representation.revision_id,
        name=representation.name,
        media_type=representation.media_type,
        blob_id=representation.blob_id,
        created_at=_iso(representation.created_at),
        blob=serialize_blob(representation.blob) if representation.blob is not None else None,
    )


def serialize_revision(revision: Revision) -> RevisionResponse:
    return RevisionResponse(
        id=revision.id,
        asset_id=revision.asset_id,
        number=revision.number,
        comment=revision.comment,
        created_by_user_id=revision.created_by_user_id,
        created_at=_iso(revision.created_at),
        representations=[serialize_representation(item) for item in revision.representations],
    )


def serialize_asset(asset: Asset) -> AssetResponse:
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


def serialize_metadata(entry: MetadataEntry) -> MetadataResponse:
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


def serialize_plugin(plugin: PluginRecord) -> PluginResponse:
    return PluginResponse(
        id=plugin.id,
        name=plugin.name,
        version=plugin.version,
        type=plugin.plugin_type,
        capabilities=plugin.capabilities,
        enabled=plugin.enabled,
        created_at=_iso(plugin.created_at),
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
    target = db.get(SessionToken, session_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
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


@router.post("/organizations", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
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


@router.post("/organizations/{organization_id}/members", response_model=OrganizationMembershipResponse)
def add_organization_member(
    organization_id: str,
    payload: AddOrganizationMemberRequest,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> OrganizationMembershipResponse:
    membership = OrganizationModule.add_member(
        db,
        organization_id=organization_id,
        user_id=payload.user_id,
        role=payload.role,
        actor=context.user,
    )
    db.commit()
    db.refresh(membership)
    return OrganizationMembershipResponse(id=membership.id, role=membership.role)


@router.get("/organizations/{organization_id}/members", response_model=list[OrganizationMembershipResponse])
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


@router.get("/organizations/{organization_id}/projects/me", response_model=list[ProjectMembershipResponse])
def list_user_projects(
    organization_id: str,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> list[ProjectMembershipResponse]:
    return [
        ProjectMembershipResponse(id=item.id, role=item.role, project=serialize_project(item.project))
        for item in ProjectModule.list_user_projects(db, organization_id=organization_id, actor=context.user)
    ]


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: str,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> ProjectResponse:
    return serialize_project(ProjectModule.get_project(db, project_id=project_id, actor=context.user))


@router.post("/projects/{project_id}/members", response_model=ProjectMembershipResponse)
def add_project_member(
    project_id: str,
    payload: AddProjectMemberRequest,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> ProjectMembershipResponse:
    membership = ProjectModule.add_member(
        db, project_id=project_id, user_id=payload.user_id, role=payload.role, actor=context.user
    )
    db.commit()
    return ProjectMembershipResponse(id=membership.id, role=membership.role)


@router.get("/projects/{project_id}/members", response_model=list[ProjectMembershipResponse])
def list_project_members(
    project_id: str,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> list[ProjectMembershipResponse]:
    memberships = ProjectModule.list_members(db, project_id=project_id, actor=context.user)
    return [ProjectMembershipResponse(id=item.id, role=item.role, user=serialize_user(item.user)) for item in memberships]


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
    del context
    blob, content = BlobModule.download_blob(db, blob_id=blob_id, storage=storage)
    return Response(
        content=content,
        media_type=blob.media_type,
        headers={"Content-Disposition": f'attachment; filename="{blob.filename}"'},
    )


@router.post("/projects/{project_id}/assets", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
def create_asset(
    project_id: str,
    payload: CreateAssetRequest,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> AssetResponse:
    asset = AssetsModule.create_asset(
        db, project_id=project_id, name=payload.name, description=payload.description, actor=context.user
    )
    db.commit()
    return serialize_asset(asset)


@router.get("/projects/{project_id}/assets", response_model=list[AssetResponse])
def list_assets(
    project_id: str,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> list[AssetResponse]:
    return [serialize_asset(item) for item in AssetsModule.list_assets(db, project_id=project_id, actor=context.user)]


@router.get("/assets/{asset_id}", response_model=AssetResponse)
def get_asset(
    asset_id: str,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> AssetResponse:
    return serialize_asset(AssetsModule.get_asset(db, asset_id=asset_id, actor=context.user))


@router.get("/assets/{asset_id}/history", response_model=list[RevisionResponse])
def get_asset_history(
    asset_id: str,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> list[RevisionResponse]:
    return [serialize_revision(item) for item in AssetsModule.list_history(db, asset_id=asset_id, actor=context.user)]


@router.post("/assets/{asset_id}/revisions", response_model=RevisionResponse, status_code=status.HTTP_201_CREATED)
def create_revision(
    asset_id: str,
    payload: CreateRevisionRequest,
    context: SessionContext = Depends(get_authenticated_session),
    db: Session = Depends(get_db_session),
) -> RevisionResponse:
    revision = AssetsModule.create_revision(db, asset_id=asset_id, comment=payload.comment, actor=context.user)
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid lifecycle status.")
    asset = AssetsModule.update_status(db, asset_id=asset_id, status_value=payload.status, actor=context.user)
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
        for item in MetadataModule.list_entries(db, target_type=target_type, target_id=target_id, actor=context.user)
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
    plugin = PluginsModule.set_plugin_enabled(db, plugin_id=plugin_id, enabled=payload.enabled, actor=context.user)
    db.commit()
    return serialize_plugin(plugin)


@asynccontextmanager
async def application_lifespan(app: FastAPI) -> Generator[None, None, None]:
    initialize_database()
    build_blob_storage()
    yield
