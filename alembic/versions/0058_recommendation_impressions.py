"""recommendation_impressions table

Revision ID: 0058
Revises: 0057
Create Date: 2026-04-26
"""

import sqlalchemy as sa
from alembic import op

revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recommendation_impressions",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "users.id", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column(
            "track_id",
            sa.Integer(),
            sa.ForeignKey(
                "tracks.id", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column(
            "surface",
            sa.String(32),
            nullable=False,
        ),
        sa.Column(
            "algorithm_version",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "position",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "recommendation_id",
            sa.String(36),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_rec_impressions_user_surface",
        "recommendation_impressions",
        ["user_id", "surface", "created_at"],
    )
    op.create_index(
        "ix_rec_impressions_recommendation_id",
        "recommendation_impressions",
        ["recommendation_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_rec_impressions_recommendation_id",
        "recommendation_impressions",
    )
    op.drop_index(
        "ix_rec_impressions_user_surface",
        "recommendation_impressions",
    )
    op.drop_table("recommendation_impressions")
