"""lyrics job request flags for cascade fallback

Revision ID: 0061
Revises: 0060
Create Date: 2026-04-27
"""

import sqlalchemy as sa
from alembic import op

revision = "0061"
down_revision = "0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lyrics_jobs",
        sa.Column(
            "request_with_sync",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "lyrics_jobs",
        sa.Column(
            "request_bypass_cache",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("lyrics_jobs", "request_bypass_cache")
    op.drop_column("lyrics_jobs", "request_with_sync")
