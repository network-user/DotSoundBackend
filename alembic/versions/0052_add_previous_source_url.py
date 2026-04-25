"""add previous_source_url to tracks for fallback history

Revision ID: 0052
Revises: 0051
Create Date: 2026-04-25
"""

import sqlalchemy as sa
from alembic import op

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tracks",
        sa.Column(
            "previous_source_url",
            sa.String(2048),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("tracks", "previous_source_url")
