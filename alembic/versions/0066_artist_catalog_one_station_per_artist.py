"""unique one dotsound_sc_artist_station release per artist

Revision ID: 0066
Revises: 0065
Create Date: 2026-04-29
"""

import sqlalchemy as sa

from alembic import op

revision = "0066"
down_revision = "0065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_artist_catalog_releases_one_station",
        "artist_catalog_releases",
        ["artist_id"],
        unique=True,
        postgresql_where=sa.text(
            "release_kind = 'dotsound_sc_artist_station'",
        ),
        sqlite_where=sa.text(
            "release_kind = 'dotsound_sc_artist_station'",
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_artist_catalog_releases_one_station",
        table_name="artist_catalog_releases",
    )
