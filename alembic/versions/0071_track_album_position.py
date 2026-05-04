"""tracks: album_position for stable album track order

Revision ID: 0071
Revises: 0070
Create Date: 2026-05-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0071"
down_revision = "0070"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tracks",
        sa.Column("album_position", sa.Integer(), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE tracks AS t
            SET album_position = s.pos
            FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY album_id
                           ORDER BY id
                       ) - 1 AS pos
                FROM tracks
                WHERE album_id IS NOT NULL
            ) AS s
            WHERE t.id = s.id
            """
        )
    )
    op.create_index(
        "ix_tracks_album_id_album_position",
        "tracks",
        ["album_id", "album_position"],
        unique=True,
        postgresql_where=sa.text(
            "album_id IS NOT NULL AND album_position IS NOT NULL"
        ),
        sqlite_where=sa.text(
            "album_id IS NOT NULL AND album_position IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tracks_album_id_album_position",
        table_name="tracks",
    )
    op.drop_column("tracks", "album_position")
