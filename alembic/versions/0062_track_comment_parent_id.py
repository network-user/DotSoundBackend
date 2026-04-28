"""track_comments parent_id for replies

Revision ID: 0062
Revises: 0061
Create Date: 2026-04-28
"""

import sqlalchemy as sa
from alembic import op

revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "track_comments",
        sa.Column(
            "parent_id",
            sa.BigInteger(),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_track_comments_parent_id",
        "track_comments",
        "track_comments",
        ["parent_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_track_comments_parent_id",
        "track_comments",
        ["parent_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_track_comments_parent_id",
        table_name="track_comments",
    )
    op.drop_constraint(
        "fk_track_comments_parent_id",
        "track_comments",
        type_="foreignkey",
    )
    op.drop_column("track_comments", "parent_id")
