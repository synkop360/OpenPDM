"""Add Phase 4 platform administration and plugin lifecycle state.

Revision ID: 20260711_0001
Revises: None
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260711_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_platform_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        sa.text(
            """
            UPDATE users
            SET is_platform_admin = TRUE
            WHERE id = (
                SELECT id FROM users WHERE is_active = TRUE ORDER BY created_at ASC, id ASC LIMIT 1
            )
            """
        )
    )
    op.add_column(
        "plugins",
        sa.Column("extension_api_versions", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "plugins", sa.Column("component", sa.String(length=255), nullable=False, server_default="")
    )
    op.add_column(
        "plugins",
        sa.Column("package_digest", sa.String(length=64), nullable=False, server_default=""),
    )
    op.add_column(
        "plugins",
        sa.Column(
            "lifecycle_state", sa.String(length=32), nullable=False, server_default="disabled"
        ),
    )
    op.add_column("plugins", sa.Column("diagnostic_reason", sa.Text(), nullable=True))
    op.add_column("plugins", sa.Column("installed_by_user_id", sa.String(length=36), nullable=True))
    op.add_column("plugins", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(sa.text("UPDATE plugins SET updated_at = created_at WHERE updated_at IS NULL"))
    op.alter_column("plugins", "updated_at", nullable=False)
    op.create_index("ix_plugins_package_digest", "plugins", ["package_digest"])
    op.create_index("ix_plugins_lifecycle_state", "plugins", ["lifecycle_state"])
    op.create_index("ix_plugins_installed_by_user_id", "plugins", ["installed_by_user_id"])
    op.create_foreign_key(
        "fk_plugins_installed_by_user_id_users",
        "plugins",
        "users",
        ["installed_by_user_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_plugins_installed_by_user_id_users", "plugins", type_="foreignkey")
    op.drop_index("ix_plugins_installed_by_user_id", table_name="plugins")
    op.drop_index("ix_plugins_lifecycle_state", table_name="plugins")
    op.drop_index("ix_plugins_package_digest", table_name="plugins")
    for column in (
        "updated_at",
        "installed_by_user_id",
        "diagnostic_reason",
        "lifecycle_state",
        "package_digest",
        "component",
        "extension_api_versions",
    ):
        op.drop_column("plugins", column)
    op.drop_column("users", "is_platform_admin")
