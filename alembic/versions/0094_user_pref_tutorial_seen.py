"""user_preferences: tutorial_seen_at flag for post-onboarding intro.

Revision ID: 0094
Revises: 0093
Create Date: 2026-05-11
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0094"
down_revision = "0093"
branch_labels = None
depends_on = None

_TABLE = "user_preferences"


def upgrade() -> None:
    op.add_column(
        _TABLE,
        sa.Column(
            "tutorial_seen_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(_TABLE, "tutorial_seen_at")
