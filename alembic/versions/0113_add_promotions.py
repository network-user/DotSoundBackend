"""Add promotions + promotion_events tables for editorial boosts.

Revision ID: 0113
Revises: 0112
Create Date: 2026-05-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0113"
down_revision: str | None = "0112"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "promotions",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "entity_type",
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column(
            "entity_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "surfaces",
            sa.JSON(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "starts_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "ends_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "title_override",
            sa.String(length=256),
            nullable=True,
        ),
        sa.Column(
            "subtitle_override",
            sa.String(length=512),
            nullable=True,
        ),
        sa.Column(
            "cta_label_override",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column(
            "cover_url_override",
            sa.String(length=1024),
            nullable=True,
        ),
        sa.Column(
            "created_by_id",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "updated_by_id",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "entity_type IN ('artist','track','playlist','album')",
            name="ck_promotions_entity_type",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_promotions_active_window",
        "promotions",
        ["is_active", "starts_at", "ends_at"],
    )
    op.create_index(
        "ix_promotions_entity",
        "promotions",
        ["entity_type", "entity_id"],
    )
    op.create_index(
        "ix_promotions_priority",
        "promotions",
        ["priority"],
    )

    op.create_table(
        "promotion_events",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "promotion_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column(
            "surface",
            sa.String(length=16),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_type IN ('impression','click')",
            name="ck_promotion_events_event_type",
        ),
        sa.ForeignKeyConstraint(
            ["promotion_id"],
            ["promotions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_promotion_events_promotion",
        "promotion_events",
        ["promotion_id", "event_type", "occurred_at"],
    )
    op.create_index(
        "ix_promotion_events_occurred_at",
        "promotion_events",
        ["occurred_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_promotion_events_occurred_at",
        table_name="promotion_events",
    )
    op.drop_index(
        "ix_promotion_events_promotion",
        table_name="promotion_events",
    )
    op.drop_table("promotion_events")
    op.drop_index(
        "ix_promotions_priority",
        table_name="promotions",
    )
    op.drop_index(
        "ix_promotions_entity",
        table_name="promotions",
    )
    op.drop_index(
        "ix_promotions_active_window",
        table_name="promotions",
    )
    op.drop_table("promotions")
