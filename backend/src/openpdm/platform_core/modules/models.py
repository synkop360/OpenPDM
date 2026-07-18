"""SQLAlchemy models for the OpenPDM Platform Core."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from openpdm.infrastructure.database import Base


def new_id() -> str:
    """Return a stable string identifier."""
    return str(uuid4())


def now() -> datetime:
    """Return the current UTC time."""
    return datetime.now(UTC)


class User(Base):
    """Local identity model for Phase 1."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(512))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )


class SessionToken(Base):
    """Server-side session with an opaque token."""

    __tablename__ = "session_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship()


class Organization(Base):
    """Tenant root for Projects."""

    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )


class OrganizationMembership(Base):
    """Membership and role assignment at the Organization level."""

    __tablename__ = "organization_memberships"
    __table_args__ = (UniqueConstraint("organization_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )

    organization: Mapped[Organization] = relationship()
    user: Mapped[User] = relationship()


class Project(Base):
    """Project owned by an Organization."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )

    organization: Mapped[Organization] = relationship()


class ProjectMembership(Base):
    """Project-level role assignment for Organization members."""

    __tablename__ = "project_memberships"
    __table_args__ = (UniqueConstraint("project_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )

    project: Mapped[Project] = relationship()
    user: Mapped[User] = relationship()


class ProjectAssetView(Base):
    """Private per-user Asset collection view within a Project."""

    __tablename__ = "project_asset_views"
    __table_args__ = (UniqueConstraint("owner_user_id", "project_id", "name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    filters: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    sort: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    density: Mapped[str] = mapped_column(String(32), default="comfortable")
    selected_columns: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )

    owner: Mapped[User] = relationship()
    project: Mapped[Project] = relationship()


class Blob(Base):
    """Blob record coordinated independently from lifecycle semantics."""

    __tablename__ = "blobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    storage_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    filename: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    checksum_sha256: Mapped[str] = mapped_column(String(64), index=True)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )

    created_by: Mapped[User] = relationship()
    representations: Mapped[list["Representation"]] = relationship(back_populates="blob")


class BlobUploadSession(Base):
    """Resumable Blob transfer owned by the Blobs Platform Module."""

    __tablename__ = "blob_upload_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(255))
    total_size_bytes: Mapped[int] = mapped_column(BigInteger)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    chunk_size_bytes: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    blob_id: Mapped[str | None] = mapped_column(ForeignKey("blobs.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )

    owner: Mapped[User] = relationship()
    blob: Mapped[Blob | None] = relationship()
    chunks: Mapped[list["BlobUploadChunk"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class BlobUploadChunk(Base):
    """Verified metadata for one persisted upload-session chunk."""

    __tablename__ = "blob_upload_chunks"
    __table_args__ = (UniqueConstraint("session_id", "chunk_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("blob_upload_sessions.id"), index=True)
    chunk_number: Mapped[int] = mapped_column(Integer)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )

    session: Mapped[BlobUploadSession] = relationship(back_populates="chunks")


class Asset(Base):
    """Stable identity of a managed Engineering Asset."""

    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="draft")
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )

    project: Mapped[Project] = relationship()
    revisions: Mapped[list["Revision"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )
    collaboration_lock: Mapped["AssetCollaborationLock | None"] = relationship(
        back_populates="asset", cascade="all, delete-orphan", uselist=False
    )


class AssetRelationship(Base):
    """Generic Phase 3 relationship between two Assets."""

    __tablename__ = "asset_relationships"
    __table_args__ = (UniqueConstraint("source_asset_id", "target_asset_id", "relationship_type"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    target_asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    relationship_type: Mapped[str] = mapped_column(String(64), index=True)
    direction: Mapped[str] = mapped_column(String(32), default="directed", nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )

    source_asset: Mapped[Asset] = relationship(foreign_keys=[source_asset_id])
    target_asset: Mapped[Asset] = relationship(foreign_keys=[target_asset_id])
    created_by: Mapped[User] = relationship()


class AssetReference(Base):
    """Generic Phase 3 external or unresolved pointer from an Asset."""

    __tablename__ = "asset_references"
    __table_args__ = (UniqueConstraint("source_asset_id", "reference_type", "target_uri"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    reference_type: Mapped[str] = mapped_column(String(64), index=True)
    target_uri: Mapped[str] = mapped_column(Text)
    label: Mapped[str] = mapped_column(String(255), default="")
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )

    source_asset: Mapped[Asset] = relationship(foreign_keys=[source_asset_id])
    created_by: Mapped[User] = relationship()


class Revision(Base):
    """Immutable state of an Asset."""

    __tablename__ = "revisions"
    __table_args__ = (UniqueConstraint("asset_id", "number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(Text, default="")
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )

    asset: Mapped[Asset] = relationship(back_populates="revisions")
    representations: Mapped[list["Representation"]] = relationship(
        back_populates="revision", cascade="all, delete-orphan"
    )


class Representation(Base):
    """Technical view of a Revision."""

    __tablename__ = "representations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    revision_id: Mapped[str] = mapped_column(ForeignKey("revisions.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(255))
    blob_id: Mapped[str | None] = mapped_column(ForeignKey("blobs.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )

    revision: Mapped[Revision] = relationship(back_populates="representations")
    blob: Mapped[Blob | None] = relationship(back_populates="representations")


class MetadataEntry(Base):
    """Generic metadata entry with no Platform Core business semantics."""

    __tablename__ = "metadata_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id"), index=True)
    revision_id: Mapped[str | None] = mapped_column(ForeignKey("revisions.id"), index=True)
    representation_id: Mapped[str | None] = mapped_column(
        ForeignKey("representations.id"), index=True
    )
    key: Mapped[str] = mapped_column(String(255), index=True)
    value: Mapped[object] = mapped_column(JSON)
    value_type: Mapped[str] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(64), default="user")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )


class AssetCollaborationLock(Base):
    """Active collaboration lock for a Phase 2 Asset workflow."""

    __tablename__ = "asset_collaboration_locks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), unique=True, index=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )

    asset: Mapped[Asset] = relationship(back_populates="collaboration_lock")
    owner: Mapped[User] = relationship()


class AuditRecord(Base):
    """Audit record for significant business actions."""

    __tablename__ = "audit_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(255), index=True)
    resource_type: Mapped[str] = mapped_column(String(64), index=True)
    resource_id: Mapped[str] = mapped_column(String(255), index=True)
    organization_id: Mapped[str | None] = mapped_column(String(36), index=True)
    project_id: Mapped[str | None] = mapped_column(String(36), index=True)
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )


class DomainEvent(Base):
    """Domain event emitted for significant Platform Core actions."""

    __tablename__ = "domain_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_type: Mapped[str] = mapped_column(String(255), index=True)
    resource_type: Mapped[str] = mapped_column(String(64), index=True)
    resource_id: Mapped[str] = mapped_column(String(255), index=True)
    organization_id: Mapped[str | None] = mapped_column(String(36), index=True)
    project_id: Mapped[str | None] = mapped_column(String(36), index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    emitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )


class NotificationRecord(Base):
    """Per-user in-app notification for Phase 2 collaboration flows."""

    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    recipient_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    organization_id: Mapped[str | None] = mapped_column(String(36), index=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    asset_id: Mapped[str | None] = mapped_column(String(36), index=True)
    revision_id: Mapped[str | None] = mapped_column(String(36), index=True)
    event_type: Mapped[str] = mapped_column(String(255), index=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )

    recipient: Mapped[User] = relationship(foreign_keys=[recipient_user_id])
    actor: Mapped[User | None] = relationship(foreign_keys=[actor_user_id])


class PluginRecord(Base):
    """Governed Phase 4 plugin registry and lifecycle record."""

    __tablename__ = "plugins"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    version: Mapped[str] = mapped_column(String(64))
    plugin_type: Mapped[str] = mapped_column(String(64))
    capabilities: Mapped[list[str]] = mapped_column(JSON, default=list)
    event_subscriptions: Mapped[list[str]] = mapped_column(JSON, default=list)
    configuration_schema: Mapped[dict[str, object] | None] = mapped_column(JSON)
    extension_api_versions: Mapped[list[int]] = mapped_column(JSON, default=list)
    component: Mapped[str] = mapped_column(String(255), default="")
    package_digest: Mapped[str] = mapped_column(String(64), default="", index=True)
    lifecycle_state: Mapped[str] = mapped_column(String(32), default="installed", index=True)
    diagnostic_reason: Mapped[str | None] = mapped_column(Text)
    installed_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )

    installed_by: Mapped[User | None] = relationship()


class PluginConfiguration(Base):
    """Deployment-scoped plugin configuration with separately encrypted secrets."""

    __tablename__ = "plugin_configurations"

    plugin_id: Mapped[str] = mapped_column(ForeignKey("plugins.id"), primary_key=True)
    public_values: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    encrypted_secrets: Mapped[str | None] = mapped_column(Text)
    updated_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )

    plugin: Mapped[PluginRecord] = relationship()
    updated_by: Mapped[User] = relationship()


class PluginEventDelivery(Base):
    """At-least-once post-commit delivery state for one plugin event handler."""

    __tablename__ = "plugin_event_deliveries"
    __table_args__ = (UniqueConstraint("plugin_id", "domain_event_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    plugin_id: Mapped[str] = mapped_column(ForeignKey("plugins.id"), index=True)
    domain_event_id: Mapped[str] = mapped_column(ForeignKey("domain_events.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(255), index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False, index=True
    )
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )

    plugin: Mapped[PluginRecord] = relationship()
    domain_event: Mapped[DomainEvent] = relationship()
