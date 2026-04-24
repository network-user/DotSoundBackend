"""add user_linked_accounts for OAuth provider connections

Revision ID: 0050
Revises: 0049
Create Date: 2026-04-24
"""

import sqlalchemy as sa
from alembic import op

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_linked_accounts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_user_id", sa.String(255), nullable=True),
        sa.Column("provider_username", sa.String(255), nullable=True),
        sa.Column("access_token_encrypted", sa.Text, nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text, nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scopes", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_user_linked_accounts_user_id",
        "user_linked_accounts",
        ["user_id"],
    )
    op.create_unique_constraint(
        "uq_linked_account_user_provider",
        "user_linked_accounts",
        ["user_id", "provider"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_linked_account_user_provider",
        "user_linked_accounts",
        type_="unique",
    )
    op.drop_index(
        "ix_user_linked_accounts_user_id",
        table_name="user_linked_accounts",
    )
    op.drop_table("user_linked_accounts")
