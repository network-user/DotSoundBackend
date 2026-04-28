"""artist catalog tables and SoundCloud ids on artists

Revision ID: 0063
Revises: 0062
Create Date: 2026-04-28
"""

import sqlalchemy as sa

from alembic import op

revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "artists",
        sa.Column(
            "soundcloud_user_id",
            sa.BigInteger(),
            nullable=True,
        ),
    )
    op.add_column(
        "artists",
        sa.Column(
            "soundcloud_permalink",
            sa.String(256),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_artists_soundcloud_user_id",
        "artists",
        ["soundcloud_user_id"],
    )
    op.create_index(
        "ix_artists_soundcloud_permalink",
        "artists",
        ["soundcloud_permalink"],
    )

    op.create_table(
        "artist_catalog_releases",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
            primary_key=True,
        ),
        sa.Column(
            "artist_id",
            sa.Integer(),
            sa.ForeignKey("artists.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("release_kind", sa.String(32), nullable=True),
        sa.Column("cover_key", sa.Text(), nullable=True),
        sa.Column("released_at", sa.Date(), nullable=True),
        sa.Column(
            "soundcloud_album_id",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "display_position",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "manual_lock",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_artist_catalog_releases_artist_id",
        "artist_catalog_releases",
        ["artist_id"],
    )
    op.create_index(
        "ix_artist_catalog_releases_artist_display_pos",
        "artist_catalog_releases",
        ["artist_id", "display_position"],
    )
    op.create_index(
        "uq_artist_catalog_releases_artist_sc_album",
        "artist_catalog_releases",
        ["artist_id", "soundcloud_album_id"],
        unique=True,
        postgresql_where=sa.text("soundcloud_album_id IS NOT NULL"),
    )

    op.create_table(
        "artist_catalog_release_tracks",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
            primary_key=True,
        ),
        sa.Column(
            "release_id",
            sa.Integer(),
            sa.ForeignKey(
                "artist_catalog_releases.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "track_id",
            sa.Integer(),
            sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.UniqueConstraint(
            "release_id",
            "track_id",
            name="uq_catalog_release_track",
        ),
        sa.UniqueConstraint(
            "release_id",
            "position",
            name="uq_catalog_release_position",
        ),
    )
    op.create_index(
        "ix_artist_catalog_release_tracks_release_id",
        "artist_catalog_release_tracks",
        ["release_id"],
    )
    op.create_index(
        "ix_artist_catalog_release_tracks_track_id",
        "artist_catalog_release_tracks",
        ["track_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_artist_catalog_release_tracks_track_id",
        table_name="artist_catalog_release_tracks",
    )
    op.drop_index(
        "ix_artist_catalog_release_tracks_release_id",
        table_name="artist_catalog_release_tracks",
    )
    op.drop_table("artist_catalog_release_tracks")

    op.drop_index(
        "uq_artist_catalog_releases_artist_sc_album",
        table_name="artist_catalog_releases",
    )
    op.drop_index(
        "ix_artist_catalog_releases_artist_display_pos",
        table_name="artist_catalog_releases",
    )
    op.drop_index(
        "ix_artist_catalog_releases_artist_id",
        table_name="artist_catalog_releases",
    )
    op.drop_table("artist_catalog_releases")

    op.drop_index(
        "ix_artists_soundcloud_permalink",
        table_name="artists",
    )
    op.drop_index(
        "ix_artists_soundcloud_user_id",
        table_name="artists",
    )
    op.drop_column("artists", "soundcloud_permalink")
    op.drop_column("artists", "soundcloud_user_id")
