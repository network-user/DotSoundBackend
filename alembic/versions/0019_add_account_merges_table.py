"""add account merges table

Revision ID: 0019
Revises: 0018
Create Date: 2026-04-13
"""

from alembic import op
import sqlalchemy as sa

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_merges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "source_user_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "users.id", ondelete="SET NULL"
            ),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "target_user_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "users.id", ondelete="SET NULL"
            ),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "merged_data_summary",
            sa.Text(),
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


def downgrade() -> None:
    op.drop_table("account_merges")
