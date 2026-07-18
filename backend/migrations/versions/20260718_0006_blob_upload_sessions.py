"""add resumable Blob upload sessions

Revision ID: 20260718_0006
Revises: 20260718_0005
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_0006"
down_revision: str | None = "20260718_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("blobs") as batch_op:
        batch_op.alter_column("size_bytes", existing_type=sa.Integer(), type_=sa.BigInteger())
    op.create_table(
        "blob_upload_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_user_id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=255), nullable=False),
        sa.Column("total_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("chunk_size_bytes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("blob_id", sa.String(length=36), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["blob_id"], ["blobs.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_blob_upload_sessions_owner_user_id"), "blob_upload_sessions", ["owner_user_id"]
    )
    op.create_index(op.f("ix_blob_upload_sessions_status"), "blob_upload_sessions", ["status"])
    op.create_index(op.f("ix_blob_upload_sessions_blob_id"), "blob_upload_sessions", ["blob_id"])
    op.create_index(
        op.f("ix_blob_upload_sessions_expires_at"), "blob_upload_sessions", ["expires_at"]
    )
    op.create_table(
        "blob_upload_chunks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("chunk_number", sa.Integer(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["blob_upload_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "chunk_number"),
    )
    op.create_index(op.f("ix_blob_upload_chunks_session_id"), "blob_upload_chunks", ["session_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_blob_upload_chunks_session_id"), table_name="blob_upload_chunks")
    op.drop_table("blob_upload_chunks")
    for name in ("expires_at", "blob_id", "status", "owner_user_id"):
        op.drop_index(op.f(f"ix_blob_upload_sessions_{name}"), table_name="blob_upload_sessions")
    op.drop_table("blob_upload_sessions")
    with op.batch_alter_table("blobs") as batch_op:
        batch_op.alter_column("size_bytes", existing_type=sa.BigInteger(), type_=sa.Integer())
