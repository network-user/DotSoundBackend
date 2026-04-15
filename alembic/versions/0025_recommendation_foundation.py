"""recommendation foundation

Revision ID: 0025
Revises: 0024
Create Date: 2026-04-15
"""

from alembic import op
import sqlalchemy as sa

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "artists",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "name", sa.String(256), nullable=False
        ),
        sa.Column(
            "name_normalized",
            sa.String(256),
            nullable=False,
        ),
        sa.Column("image_key", sa.Text, nullable=True),
        sa.Column(
            "source",
            sa.String(20),
            server_default="internal",
            nullable=False,
        ),
        sa.Column(
            "external_id",
            sa.String(256),
            nullable=True,
        ),
        sa.Column("bio", sa.Text, nullable=True),
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
        "ix_artists_name_normalized",
        "artists",
        ["name_normalized"],
    )

    op.create_table(
        "track_artists",
        sa.Column(
            "track_id",
            sa.Integer,
            sa.ForeignKey(
                "tracks.id", ondelete="CASCADE"
            ),
            primary_key=True,
        ),
        sa.Column(
            "artist_id",
            sa.Integer,
            sa.ForeignKey(
                "artists.id", ondelete="CASCADE"
            ),
            primary_key=True,
        ),
        sa.Column(
            "role",
            sa.String(20),
            server_default="primary",
            nullable=False,
        ),
        sa.Column(
            "position",
            sa.Integer,
            server_default="0",
            nullable=False,
        ),
        sa.UniqueConstraint(
            "track_id",
            "artist_id",
            name="uq_track_artist",
        ),
    )
    op.create_index(
        "ix_track_artists_artist_id",
        "track_artists",
        ["artist_id"],
    )

    op.create_table(
        "user_preferences",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey(
                "users.id", ondelete="CASCADE"
            ),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "preferred_genres", sa.JSON, nullable=True
        ),
        sa.Column(
            "preferred_artist_ids",
            sa.JSON,
            nullable=True,
        ),
        sa.Column(
            "preferred_moods", sa.JSON, nullable=True
        ),
        sa.Column(
            "onboarding_completed",
            sa.Boolean,
            server_default="false",
            nullable=False,
        ),
        sa.Column(
            "calibration_completed",
            sa.Boolean,
            server_default="false",
            nullable=False,
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

    op.create_table(
        "listen_events",
        sa.Column(
            "id",
            sa.BigInteger,
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey(
                "users.id", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column(
            "track_id",
            sa.Integer,
            sa.ForeignKey(
                "tracks.id", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "duration_listened_seconds",
            sa.Integer,
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "total_duration_seconds",
            sa.Integer,
            nullable=True,
        ),
        sa.Column(
            "completed",
            sa.Boolean,
            server_default="false",
            nullable=False,
        ),
        sa.Column(
            "skipped",
            sa.Boolean,
            server_default="false",
            nullable=False,
        ),
        sa.Column(
            "source_context",
            sa.String(30),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_listen_events_user_created",
        "listen_events",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_listen_events_track_created",
        "listen_events",
        ["track_id", "created_at"],
    )

    op.create_table(
        "search_events",
        sa.Column(
            "id",
            sa.BigInteger,
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey(
                "users.id", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column(
            "query",
            sa.String(256),
            nullable=False,
        ),
        sa.Column(
            "results_count",
            sa.Integer,
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "clicked_track_id",
            sa.Integer,
            sa.ForeignKey(
                "tracks.id", ondelete="SET NULL"
            ),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_search_events_user_created",
        "search_events",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("search_events")
    op.drop_table("listen_events")
    op.drop_table("user_preferences")
    op.drop_table("track_artists")
    op.drop_table("artists")
