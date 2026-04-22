"""add user_track_library many-to-many table

Lets a single canonical Track appear in every importing user's
library without losing the original ``uploaded_by_id`` provenance.
Composite PK ``(user_id, track_id)`` plus ``ON CONFLICT DO NOTHING``
inserts make the link idempotent for repeated imports of the same
track by the same user.

Backfills the new table from existing ``tracks.uploaded_by_id``
so that current users keep seeing the tracks they already had.

Revision ID: 0047
Revises: 0046
Create Date: 2026-04-22
"""

import sqlalchemy as sa

from alembic import op

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_track_library",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("track_id", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=True),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["track_id"], ["tracks.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "track_id"),
    )
    op.create_index(
        "ix_user_track_library_user_id_imported_at",
        "user_track_library",
        ["user_id", "imported_at"],
    )
    op.execute(
        "INSERT INTO user_track_library "
        "(user_id, track_id, source, imported_at) "
        "SELECT uploaded_by_id, id, "
        "COALESCE(imported_from, 'upload'), "
        "COALESCE(created_at, NOW()) "
        "FROM tracks "
        "WHERE uploaded_by_id IS NOT NULL "
        "ON CONFLICT DO NOTHING"
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_track_library_user_id_imported_at",
        table_name="user_track_library",
    )
    op.drop_table("user_track_library")
