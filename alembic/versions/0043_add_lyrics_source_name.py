"""add track_lyrics.source_name

Revision ID: 0043
Revises: 0042
Create Date: 2026-04-21
"""

from alembic import op
import sqlalchemy as sa

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "track_lyrics",
        sa.Column(
            "source_name",
            sa.String(length=50),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("track_lyrics", "source_name")
