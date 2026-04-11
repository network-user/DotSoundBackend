"""add video_key to tracks

Revision ID: 0013
Revises: 0012
Create Date: 2026-04-11
"""

from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tracks",
        sa.Column("video_key", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tracks", "video_key")
