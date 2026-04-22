"""add track_lyrics.sync_source_name

Adds a separate attribution field for the provider that supplied
the time-aligned synced lines, distinct from ``source_name`` which
keeps tracking the provider that supplied the lyrics text. Both
fields are nullable; PrivateCore decides what label to put in each.

Revision ID: 0046
Revises: 0045
Create Date: 2026-04-22
"""

import sqlalchemy as sa

from alembic import op

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "track_lyrics",
        sa.Column(
            "sync_source_name",
            sa.String(length=50),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("track_lyrics", "sync_source_name")
