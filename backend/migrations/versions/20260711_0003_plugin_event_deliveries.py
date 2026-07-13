"""Add durable at-least-once plugin event deliveries.

Revision ID: 20260711_0003
Revises: 20260711_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260711_0003"
down_revision: str | None = "20260711_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(table: str) -> bool:
    if op.get_context().as_sql:
        return False
    return sa.inspect(op.get_bind()).has_table(table)


def upgrade() -> None:
    if _has_table("plugin_event_deliveries"):
        return
    op.create_table(
        "plugin_event_deliveries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("plugin_id", sa.String(length=255), nullable=False),
        sa.Column("domain_event_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["domain_event_id"],
            ["domain_events.id"],
            name="fk_plugin_event_deliveries_domain_event_id_domain_events",
        ),
        sa.ForeignKeyConstraint(
            ["plugin_id"], ["plugins.id"], name="fk_plugin_event_deliveries_plugin_id_plugins"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_plugin_event_deliveries"),
        sa.UniqueConstraint(
            "plugin_id",
            "domain_event_id",
            name="uq_plugin_event_deliveries_plugin_id",
        ),
    )
    for column in ("plugin_id", "domain_event_id", "event_type", "status", "next_attempt_at"):
        op.create_index(f"ix_plugin_event_deliveries_{column}", "plugin_event_deliveries", [column])


def downgrade() -> None:
    op.drop_table("plugin_event_deliveries")
