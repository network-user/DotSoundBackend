"""add email auth fields

Revision ID: 0018
Revises: 0017
Create Date: 2026-04-13
"""

from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "email",
            sa.String(255),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "email_verified",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "auth_provider",
            sa.String(20),
            server_default="telegram",
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "totp_secret_encrypted",
            sa.Text(),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "totp_enabled",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "backup_codes_hash",
            sa.Text(),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_users_email",
        "users",
        ["email"],
        unique=True,
    )

    op.alter_column(
        "users",
        "telegram_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )

    op.create_check_constraint(
        "ck_users_has_identity",
        "users",
        "telegram_id IS NOT NULL OR email IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_users_has_identity",
        "users",
        type_="check",
    )

    op.execute(
        "DELETE FROM users "
        "WHERE telegram_id IS NULL"
    )
    op.alter_column(
        "users",
        "telegram_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )

    op.drop_index("ix_users_email", table_name="users")
    op.drop_column("users", "backup_codes_hash")
    op.drop_column("users", "totp_enabled")
    op.drop_column("users", "totp_secret_encrypted")
    op.drop_column("users", "auth_provider")
    op.drop_column("users", "email_verified")
    op.drop_column("users", "email")
