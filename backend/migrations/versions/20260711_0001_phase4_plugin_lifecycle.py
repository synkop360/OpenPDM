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


def _inspector() -> sa.Inspector | None:
    if op.get_context().as_sql:
        return None
    return sa.inspect(op.get_bind())


def _has_column(table: str, column: str) -> bool:
    inspector = _inspector()
    return inspector is not None and column in {
        item["name"] for item in inspector.get_columns(table)
    }


def _has_index(table: str, index: str) -> bool:
    inspector = _inspector()
    return inspector is not None and index in {
        item["name"] for item in inspector.get_indexes(table)
    }


def _has_foreign_key(table: str, constraint: str) -> bool:
    inspector = _inspector()
    return inspector is not None and constraint in {
        item["name"] for item in inspector.get_foreign_keys(table)
    }


def upgrade() -> None:
    if not _has_column("users", "is_platform_admin"):
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
    columns = (
        sa.Column("extension_api_versions", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("component", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("package_digest", sa.String(length=64), nullable=False, server_default=""),
        sa.Column(
            "lifecycle_state", sa.String(length=32), nullable=False, server_default="disabled"
        ),
        sa.Column("diagnostic_reason", sa.Text(), nullable=True),
        sa.Column("installed_by_user_id", sa.String(length=36), nullable=True),
    )
    for column in columns:
        if not _has_column("plugins", column.name):
            op.add_column("plugins", column)
    if not _has_column("plugins", "updated_at"):
        op.add_column("plugins", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
        op.execute(sa.text("UPDATE plugins SET updated_at = created_at WHERE updated_at IS NULL"))
        op.alter_column("plugins", "updated_at", nullable=False)
    for index, column in (
        ("ix_plugins_package_digest", "package_digest"),
        ("ix_plugins_lifecycle_state", "lifecycle_state"),
        ("ix_plugins_installed_by_user_id", "installed_by_user_id"),
    ):
        if not _has_index("plugins", index):
            op.create_index(index, "plugins", [column])
    if not _has_foreign_key("plugins", "fk_plugins_installed_by_user_id_users"):
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
