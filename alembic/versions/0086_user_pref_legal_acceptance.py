"""user_preferences: legal acceptance + adult confirmation

Revision ID: 0086
Revises: 0085
Create Date: 2026-05-10
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0086"
down_revision = "0085"
branch_labels = None
depends_on = None

_TABLE = "user_preferences"


def upgrade() -> None:
    op.add_column(
        _TABLE,
        sa.Column(
            "legal_accepted_version",
            sa.String(length=32),
            nullable=True,
        ),
    )
    op.add_column(
        _TABLE,
        sa.Column(
            "legal_accepted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        _TABLE,
        sa.Column(
            "is_adult_confirmed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        _TABLE,
        sa.Column(
            "adult_confirmed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(_TABLE, "adult_confirmed_at")
    op.drop_column(_TABLE, "is_adult_confirmed")
    op.drop_column(_TABLE, "legal_accepted_at")
    op.drop_column(_TABLE, "legal_accepted_version")
