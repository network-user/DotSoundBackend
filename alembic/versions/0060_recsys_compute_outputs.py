"""recsys compute output tables

Revision ID: 0060
Revises: 0059
Create Date: 2026-04-26
"""

import sqlalchemy as sa
from alembic import op

revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "track_audio_features",
        sa.Column(
            "track_id",
            sa.Integer(),
            sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("feature_vector", sa.JSON(), nullable=True),
        sa.Column("mood_tags", sa.JSON(), nullable=True),
        sa.Column("tempo_bpm", sa.Float(), nullable=True),
        sa.Column("energy", sa.Float(), nullable=True),
        sa.Column("highlight_start_sec", sa.Float(), nullable=True),
        sa.Column(
            "feature_version",
            sa.String(32),
            nullable=False,
            server_default="v1",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            onupdate=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_table(
        "artist_features",
        sa.Column(
            "artist_id",
            sa.Integer(),
            sa.ForeignKey("artists.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("centroid_vector", sa.JSON(), nullable=True),
        sa.Column("dominant_moods", sa.JSON(), nullable=True),
        sa.Column("style_tags", sa.JSON(), nullable=True),
        sa.Column(
            "feature_version",
            sa.String(32),
            nullable=False,
            server_default="v1",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            onupdate=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_table(
        "artist_similarity",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            primary_key=True,
        ),
        sa.Column(
            "artist_id",
            sa.Integer(),
            sa.ForeignKey("artists.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "similar_artist_id",
            sa.Integer(),
            sa.ForeignKey("artists.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("reason_tags", sa.JSON(), nullable=True),
        sa.Column(
            "feature_version",
            sa.String(32),
            nullable=False,
            server_default="v1",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            onupdate=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "artist_id",
            "similar_artist_id",
            "feature_version",
            name="uq_artist_similarity_pair_version",
        ),
    )
    op.create_index(
        "ix_artist_similarity_artist_score",
        "artist_similarity",
        ["artist_id", "score"],
        postgresql_ops={"score": "DESC"},
    )
    op.create_table(
        "track_similarity",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            primary_key=True,
        ),
        sa.Column(
            "track_id",
            sa.Integer(),
            sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "similar_track_id",
            sa.Integer(),
            sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("reason_tags", sa.JSON(), nullable=True),
        sa.Column(
            "feature_version",
            sa.String(32),
            nullable=False,
            server_default="v1",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            onupdate=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "track_id",
            "similar_track_id",
            "feature_version",
            name="uq_track_similarity_pair_version",
        ),
    )
    op.create_index(
        "ix_track_similarity_track_score",
        "track_similarity",
        ["track_id", "score"],
        postgresql_ops={"score": "DESC"},
    )


def downgrade() -> None:
    op.drop_index(
        "ix_track_similarity_track_score",
        "track_similarity",
    )
    op.drop_table("track_similarity")
    op.drop_index(
        "ix_artist_similarity_artist_score",
        "artist_similarity",
    )
    op.drop_table("artist_similarity")
    op.drop_table("artist_features")
    op.drop_table("track_audio_features")
