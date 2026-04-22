"""dedupe-required UNIQUE constraints on tracks

Adds partial unique indexes on tracks.sc_url and on
(imported_from, external_id). Replaces the previous non-unique
ix_tracks_imported_from_external_id from migration 0042.

Revision ID: 0045
Revises: 0044
Create Date: 2026-04-22
"""

from alembic import op

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX uq_tracks_sc_url "
        "ON tracks (sc_url) "
        "WHERE sc_url IS NOT NULL"
    )
    op.execute("DROP INDEX IF EXISTS ix_tracks_imported_from_external_id")
    op.execute(
        "CREATE UNIQUE INDEX uq_tracks_imported_from_external_id "
        "ON tracks (imported_from, external_id) "
        "WHERE external_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_tracks_imported_from_external_id")
    op.execute(
        "CREATE INDEX IF NOT EXISTS "
        "ix_tracks_imported_from_external_id "
        "ON tracks (imported_from, external_id)"
    )
    op.execute("DROP INDEX IF EXISTS uq_tracks_sc_url")
