"""add generic analysis contribution identities

Revision ID: 20260729_0007
Revises: 20260718_0006
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260729_0007"
down_revision: str | None = "20260718_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("metadata_entries", "asset_references", "asset_relationships")


def upgrade() -> None:
    for table_name in TABLES:
        op.add_column(
            table_name,
            sa.Column("analysis_contribution_id", sa.String(length=64), nullable=True),
        )
        op.create_index(
            op.f(f"ix_{table_name}_analysis_contribution_id"),
            table_name,
            ["analysis_contribution_id"],
            unique=True,
        )


def downgrade() -> None:
    for table_name in reversed(TABLES):
        op.drop_index(op.f(f"ix_{table_name}_analysis_contribution_id"), table_name=table_name)
        op.drop_column(table_name, "analysis_contribution_id")
