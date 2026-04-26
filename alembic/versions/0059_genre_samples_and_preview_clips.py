"""genre_samples and track_preview_clips tables

Revision ID: 0059
Revises: 0058
Create Date: 2026-04-26
"""

import sqlalchemy as sa
from alembic import op

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "genre_samples",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "genre",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "track_id",
            sa.Integer(),
            sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "position",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "curated",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "genre",
            "track_id",
            name="uq_genre_samples_genre_track",
        ),
    )
    op.create_index(
        "ix_genre_samples_genre_position",
        "genre_samples",
        ["genre", "position"],
    )

    op.create_table(
        "track_preview_clips",
        sa.Column(
            "track_id",
            sa.Integer(),
            sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "start_sec",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "duration_sec",
            sa.Float(),
            nullable=False,
            server_default="15",
        ),
        sa.Column(
            "source",
            sa.String(24),
            nullable=False,
            server_default="fixed_offset",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source IN ('fixed_offset','content_based')",
            name="ck_track_preview_clips_source",
        ),
    )


def downgrade() -> None:
    op.drop_table("track_preview_clips")
    op.drop_index(
        "ix_genre_samples_genre_position",
        "genre_samples",
    )
    op.drop_table("genre_samples")
