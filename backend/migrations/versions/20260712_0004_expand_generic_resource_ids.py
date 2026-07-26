"""Allow non-UUID identities in generic audit and event resources.

Revision ID: 20260712_0004
Revises: 20260711_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260712_0004"
down_revision: str | None = "20260711_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("audit_records", "domain_events"):
        op.alter_column(
            table,
            "resource_id",
            existing_type=sa.String(length=36),
            type_=sa.String(length=255),
            existing_nullable=False,
        )


def downgrade() -> None:
    for table in ("audit_records", "domain_events"):
        op.alter_column(
            table,
            "resource_id",
            existing_type=sa.String(length=255),
            type_=sa.String(length=36),
            existing_nullable=False,
        )
