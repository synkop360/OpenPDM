"""Add plugin manifest configuration and encrypted deployment values.

Revision ID: 20260711_0002
Revises: 20260711_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260711_0002"
down_revision: str | None = "20260711_0001"
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


def _has_table(table: str) -> bool:
    inspector = _inspector()
    return inspector is not None and inspector.has_table(table)


def upgrade() -> None:
    if not _has_column("plugins", "event_subscriptions"):
        op.add_column(
            "plugins",
            sa.Column("event_subscriptions", sa.JSON(), nullable=False, server_default="[]"),
        )
    if not _has_column("plugins", "configuration_schema"):
        op.add_column("plugins", sa.Column("configuration_schema", sa.JSON(), nullable=True))
    if not _has_table("plugin_configurations"):
        op.create_table(
            "plugin_configurations",
            sa.Column("plugin_id", sa.String(length=255), nullable=False),
            sa.Column("public_values", sa.JSON(), nullable=False),
            sa.Column("encrypted_secrets", sa.Text(), nullable=True),
            sa.Column("updated_by_user_id", sa.String(length=36), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["plugin_id"], ["plugins.id"], name="fk_plugin_configurations_plugin_id_plugins"
            ),
            sa.ForeignKeyConstraint(
                ["updated_by_user_id"],
                ["users.id"],
                name="fk_plugin_configurations_updated_by_user_id_users",
            ),
            sa.PrimaryKeyConstraint("plugin_id", name="pk_plugin_configurations"),
        )
        op.create_index(
            "ix_plugin_configurations_updated_by_user_id",
            "plugin_configurations",
            ["updated_by_user_id"],
        )


def downgrade() -> None:
    op.drop_index("ix_plugin_configurations_updated_by_user_id", table_name="plugin_configurations")
    op.drop_table("plugin_configurations")
    op.drop_column("plugins", "configuration_schema")
    op.drop_column("plugins", "event_subscriptions")
