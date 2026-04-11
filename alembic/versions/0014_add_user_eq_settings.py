"""add user_eq_settings table

Revision ID: 0014
Revises: 0013
Create Date: 2026-04-11
"""

from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_eq_settings",
        sa.Column(
            "id", sa.Integer(), primary_key=True
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "users.id", ondelete="CASCADE"
            ),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "preset",
            sa.String(50),
            nullable=True,
        ),
        sa.Column(
            "bands", sa.JSON(), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("user_eq_settings")
