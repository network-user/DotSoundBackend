"""playlist auto-cover: suppress + collage timestamp

Revision ID: 0084
Revises: 0083
Create Date: 2026-05-07
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0084"
down_revision = "0083"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "playlists",
        sa.Column(
            "cover_auto_suppressed",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "playlists",
        sa.Column(
            "collage_generated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("playlists", "collage_generated_at")
    op.drop_column("playlists", "cover_auto_suppressed")
