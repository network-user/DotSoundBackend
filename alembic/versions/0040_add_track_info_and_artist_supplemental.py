"""add track_info, artist_supplemental_info tables and enrichment_confidence

Revision ID: 0040
Revises: 0039
Create Date: 2026-04-19
"""

import sqlalchemy as sa
from alembic import op

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "track_info",
        sa.Column("track_id", sa.BigInteger(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["track_id"],
            ["tracks.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("track_id"),
    )

    op.create_table(
        "artist_supplemental_info",
        sa.Column("artist_id", sa.BigInteger(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["artist_id"],
            ["artists.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("artist_id"),
    )

    op.add_column(
        "artists",
        sa.Column("enrichment_confidence", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("artists", "enrichment_confidence")
    op.drop_table("artist_supplemental_info")
    op.drop_table("track_info")
