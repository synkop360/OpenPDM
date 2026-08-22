"""Create the initial Phase 1-3 Platform Core schema.

Revision ID: 20260601_0000
Revises: None
Create Date: 2026-06-01

This is the baseline every later migration assumes already exists (several
of them, starting with 20260711_0001, guard their own changes with
_has_column/_has_table checks rather than creating these tables themselves).
It intentionally only creates the schema as it stood before Phase 4: tables
and columns owned by a later migration (plugin_configurations,
plugin_event_deliveries, project_asset_views, blob_upload_sessions,
blob_upload_chunks, and the Phase 4+ columns on users/plugins) are created by
that migration instead, not here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260601_0000"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "organizations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_organizations"),
    )
    op.create_index(op.f("ix_organizations_slug"), "organizations", ["slug"], unique=True)

    op.create_table(
        "plugins",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("plugin_type", sa.String(length=64), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_plugins"),
    )

    op.create_table(
        "session_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_session_tokens"),
    )
    op.create_index(op.f("ix_session_tokens_token"), "session_tokens", ["token"], unique=True)
    op.create_index(op.f("ix_session_tokens_user_id"), "session_tokens", ["user_id"])

    op.create_table(
        "organization_memberships",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_organization_memberships"),
        sa.UniqueConstraint("organization_id", "user_id"),
    )
    op.create_index(
        op.f("ix_organization_memberships_organization_id"),
        "organization_memberships",
        ["organization_id"],
    )
    op.create_index(
        op.f("ix_organization_memberships_user_id"), "organization_memberships", ["user_id"]
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
    )
    op.create_index(op.f("ix_projects_organization_id"), "projects", ["organization_id"])

    op.create_table(
        "project_memberships",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_project_memberships"),
        sa.UniqueConstraint("project_id", "user_id"),
    )
    op.create_index(
        op.f("ix_project_memberships_project_id"), "project_memberships", ["project_id"]
    )
    op.create_index(op.f("ix_project_memberships_user_id"), "project_memberships", ["user_id"])

    op.create_table(
        "blobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_blobs"),
    )
    op.create_index(op.f("ix_blobs_storage_key"), "blobs", ["storage_key"], unique=True)
    op.create_index(op.f("ix_blobs_checksum_sha256"), "blobs", ["checksum_sha256"])
    op.create_index(op.f("ix_blobs_created_by_user_id"), "blobs", ["created_by_user_id"])

    op.create_table(
        "assets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_assets"),
    )
    op.create_index(op.f("ix_assets_project_id"), "assets", ["project_id"])
    op.create_index(op.f("ix_assets_name"), "assets", ["name"])

    op.create_table(
        "asset_relationships",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_asset_id", sa.String(length=36), nullable=False),
        sa.Column("target_asset_id", sa.String(length=36), nullable=False),
        sa.Column("relationship_type", sa.String(length=64), nullable=False),
        sa.Column("direction", sa.String(length=32), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["source_asset_id"], ["assets.id"]),
        sa.ForeignKeyConstraint(["target_asset_id"], ["assets.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_asset_relationships"),
        sa.UniqueConstraint("source_asset_id", "target_asset_id", "relationship_type"),
    )
    op.create_index(
        op.f("ix_asset_relationships_source_asset_id"), "asset_relationships", ["source_asset_id"]
    )
    op.create_index(
        op.f("ix_asset_relationships_target_asset_id"), "asset_relationships", ["target_asset_id"]
    )
    op.create_index(
        op.f("ix_asset_relationships_relationship_type"),
        "asset_relationships",
        ["relationship_type"],
    )
    op.create_index(
        op.f("ix_asset_relationships_created_by_user_id"),
        "asset_relationships",
        ["created_by_user_id"],
    )

    op.create_table(
        "asset_references",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_asset_id", sa.String(length=36), nullable=False),
        sa.Column("reference_type", sa.String(length=64), nullable=False),
        sa.Column("target_uri", sa.Text(), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["source_asset_id"], ["assets.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_asset_references"),
        sa.UniqueConstraint("source_asset_id", "reference_type", "target_uri"),
    )
    op.create_index(
        op.f("ix_asset_references_source_asset_id"), "asset_references", ["source_asset_id"]
    )
    op.create_index(
        op.f("ix_asset_references_reference_type"), "asset_references", ["reference_type"]
    )
    op.create_index(
        op.f("ix_asset_references_created_by_user_id"), "asset_references", ["created_by_user_id"]
    )

    op.create_table(
        "revisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("asset_id", sa.String(length=36), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_revisions"),
        sa.UniqueConstraint("asset_id", "number"),
    )
    op.create_index(op.f("ix_revisions_asset_id"), "revisions", ["asset_id"])

    op.create_table(
        "representations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("revision_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=255), nullable=False),
        sa.Column("blob_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["blob_id"], ["blobs.id"]),
        sa.ForeignKeyConstraint(["revision_id"], ["revisions.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_representations"),
    )
    op.create_index(op.f("ix_representations_revision_id"), "representations", ["revision_id"])
    op.create_index(op.f("ix_representations_blob_id"), "representations", ["blob_id"])

    op.create_table(
        "metadata_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("asset_id", sa.String(length=36), nullable=True),
        sa.Column("revision_id", sa.String(length=36), nullable=True),
        sa.Column("representation_id", sa.String(length=36), nullable=True),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("value_type", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.ForeignKeyConstraint(["representation_id"], ["representations.id"]),
        sa.ForeignKeyConstraint(["revision_id"], ["revisions.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_metadata_entries"),
    )
    op.create_index(op.f("ix_metadata_entries_asset_id"), "metadata_entries", ["asset_id"])
    op.create_index(op.f("ix_metadata_entries_revision_id"), "metadata_entries", ["revision_id"])
    op.create_index(
        op.f("ix_metadata_entries_representation_id"), "metadata_entries", ["representation_id"]
    )
    op.create_index(op.f("ix_metadata_entries_key"), "metadata_entries", ["key"])

    op.create_table(
        "asset_collaboration_locks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("asset_id", sa.String(length=36), nullable=False),
        sa.Column("owner_user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_asset_collaboration_locks"),
    )
    op.create_index(
        op.f("ix_asset_collaboration_locks_asset_id"),
        "asset_collaboration_locks",
        ["asset_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_asset_collaboration_locks_owner_user_id"),
        "asset_collaboration_locks",
        ["owner_user_id"],
    )

    op.create_table(
        "audit_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=255), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=True),
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_audit_records"),
    )
    op.create_index(op.f("ix_audit_records_actor_user_id"), "audit_records", ["actor_user_id"])
    op.create_index(op.f("ix_audit_records_action"), "audit_records", ["action"])
    op.create_index(op.f("ix_audit_records_resource_type"), "audit_records", ["resource_type"])
    op.create_index(op.f("ix_audit_records_resource_id"), "audit_records", ["resource_id"])
    op.create_index(op.f("ix_audit_records_organization_id"), "audit_records", ["organization_id"])
    op.create_index(op.f("ix_audit_records_project_id"), "audit_records", ["project_id"])

    op.create_table(
        "domain_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=255), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=True),
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("emitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_domain_events"),
    )
    op.create_index(op.f("ix_domain_events_event_type"), "domain_events", ["event_type"])
    op.create_index(op.f("ix_domain_events_resource_type"), "domain_events", ["resource_type"])
    op.create_index(op.f("ix_domain_events_resource_id"), "domain_events", ["resource_id"])
    op.create_index(op.f("ix_domain_events_organization_id"), "domain_events", ["organization_id"])
    op.create_index(op.f("ix_domain_events_project_id"), "domain_events", ["project_id"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("recipient_user_id", sa.String(length=36), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("organization_id", sa.String(length=36), nullable=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("asset_id", sa.String(length=36), nullable=True),
        sa.Column("revision_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=255), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_notifications"),
    )
    op.create_index(
        op.f("ix_notifications_recipient_user_id"), "notifications", ["recipient_user_id"]
    )
    op.create_index(op.f("ix_notifications_actor_user_id"), "notifications", ["actor_user_id"])
    op.create_index(op.f("ix_notifications_organization_id"), "notifications", ["organization_id"])
    op.create_index(op.f("ix_notifications_project_id"), "notifications", ["project_id"])
    op.create_index(op.f("ix_notifications_asset_id"), "notifications", ["asset_id"])
    op.create_index(op.f("ix_notifications_revision_id"), "notifications", ["revision_id"])
    op.create_index(op.f("ix_notifications_event_type"), "notifications", ["event_type"])


def downgrade() -> None:
    for table in (
        "notifications",
        "domain_events",
        "audit_records",
        "asset_collaboration_locks",
        "metadata_entries",
        "representations",
        "revisions",
        "asset_references",
        "asset_relationships",
        "assets",
        "blobs",
        "project_memberships",
        "projects",
        "organization_memberships",
        "session_tokens",
        "plugins",
        "organizations",
        "users",
    ):
        op.drop_table(table)
