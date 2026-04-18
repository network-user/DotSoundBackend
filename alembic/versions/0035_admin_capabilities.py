"""admin capabilities + admin actions log

Revision ID: 0035
Revises: 0034
Create Date: 2026-04-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_capabilities",
        sa.Column(
            "id",
            sa.BigInteger,
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey(
                "users.id", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column(
            "capability",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "granted_by", sa.BigInteger, nullable=True
        ),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "user_id", "capability",
            name="uq_admin_capability",
        ),
    )
    op.create_index(
        "ix_admin_capabilities_user",
        "admin_capabilities",
        ["user_id"],
    )

    op.create_table(
        "admin_actions_log",
        sa.Column(
            "id",
            sa.BigInteger,
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger,
            nullable=False,
        ),
        sa.Column(
            "action",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "target_type",
            sa.String(64),
            nullable=True,
        ),
        sa.Column(
            "target_id",
            sa.String(128),
            nullable=True,
        ),
        sa.Column(
            "ip", sa.String(64), nullable=True
        ),
        sa.Column(
            "meta", sa.JSON(), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_admin_actions_log_user_time",
        "admin_actions_log",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_admin_actions_log_user_time",
        table_name="admin_actions_log",
    )
    op.drop_table("admin_actions_log")
    op.drop_index(
        "ix_admin_capabilities_user",
        table_name="admin_capabilities",
    )
    op.drop_table("admin_capabilities")
