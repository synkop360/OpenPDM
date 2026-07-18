"""add private per-user Project Asset views

Revision ID: 20260718_0005
Revises: 20260712_0004
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_0005"
down_revision: str | None = "20260712_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_asset_views",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_user_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("sort", sa.JSON(), nullable=False),
        sa.Column("density", sa.String(length=32), nullable=False),
        sa.Column("selected_columns", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "project_id", "name"),
    )
    op.create_index(
        op.f("ix_project_asset_views_owner_user_id"),
        "project_asset_views",
        ["owner_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_asset_views_project_id"),
        "project_asset_views",
        ["project_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_project_asset_views_project_id"), table_name="project_asset_views")
    op.drop_index(op.f("ix_project_asset_views_owner_user_id"), table_name="project_asset_views")
    op.drop_table("project_asset_views")
