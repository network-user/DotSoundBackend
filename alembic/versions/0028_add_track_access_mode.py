"""add track access mode and provenance

Revision ID: 0028
Revises: 0027
Create Date: 2026-04-15
"""

from alembic import op
import sqlalchemy as sa

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tracks",
        sa.Column(
            "access_mode",
            sa.String(length=32),
            server_default="internal_stream",
            nullable=False,
        ),
    )
    op.add_column(
        "tracks",
        sa.Column(
            "source_platform",
            sa.String(length=32),
            nullable=True,
        ),
    )
    op.add_column(
        "tracks",
        sa.Column(
            "canonical_source_url",
            sa.Text(),
            nullable=True,
        ),
    )

    op.execute(
        "UPDATE tracks "
        "SET access_mode = 'third_party_stream', "
        "source_platform = 'soundcloud', "
        "canonical_source_url = COALESCE(source_url, sc_url) "
        "WHERE source = 'soundcloud'"
    )
    op.execute(
        "UPDATE tracks "
        "SET source_platform = 'telegram' "
        "WHERE source = 'telegram' "
        "AND source_platform IS NULL"
    )
    op.execute(
        "UPDATE tracks "
        "SET canonical_source_url = source_url "
        "WHERE source_url IS NOT NULL "
        "AND canonical_source_url IS NULL"
    )


def downgrade() -> None:
    op.drop_column("tracks", "canonical_source_url")
    op.drop_column("tracks", "source_platform")
    op.drop_column("tracks", "access_mode")
