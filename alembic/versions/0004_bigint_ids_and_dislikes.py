"""BigInt User IDs and Dislikes table

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Alter columns to BigInteger
    # We use type_=sa.BigInteger() and explicit cast for PostgreSQL
    op.execute("ALTER TABLE users ALTER COLUMN id TYPE BIGINT")
    op.execute("ALTER TABLE tracks ALTER COLUMN uploaded_by_id TYPE BIGINT")
    op.execute("ALTER TABLE playlists ALTER COLUMN owner_id TYPE BIGINT")
    op.execute("ALTER TABLE likes ALTER COLUMN user_id TYPE BIGINT")
    op.execute("ALTER TABLE complaints ALTER COLUMN reported_by_user_id TYPE BIGINT")

    # 2. Create dislikes table
    op.create_table(
        "dislikes",
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "track_id",
            sa.Integer(),
            sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("dislikes")
    
    # Revert to Integer
    op.execute("ALTER TABLE users ALTER COLUMN id TYPE INTEGER")
    op.execute("ALTER TABLE tracks ALTER COLUMN uploaded_by_id TYPE INTEGER")
    op.execute("ALTER TABLE playlists ALTER COLUMN owner_id TYPE INTEGER")
    op.execute("ALTER TABLE likes ALTER COLUMN user_id TYPE INTEGER")
    op.execute("ALTER TABLE complaints ALTER COLUMN reported_by_user_id TYPE INTEGER")
