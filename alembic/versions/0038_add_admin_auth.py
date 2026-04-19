"""admin auth: TOTP onboarding + devices + sessions + login attempts

Revision ID: 0038
Revises: 0037
Create Date: 2026-04-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "admin_init",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "admin_totp_secret_encrypted",
            sa.Text(),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "admin_totp_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "admin_backup_codes_hash",
            sa.Text(),
            nullable=True,
        ),
    )

    op.create_table(
        "admin_devices",
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
            "fingerprint_hash",
            sa.String(128),
            nullable=False,
        ),
        sa.Column(
            "label",
            sa.String(128),
            nullable=True,
        ),
        sa.Column(
            "ip_first",
            sa.String(64),
            nullable=True,
        ),
        sa.Column(
            "ua_first",
            sa.String(512),
            nullable=True,
        ),
        sa.Column(
            "trusted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "user_id",
            "fingerprint_hash",
            name="uq_admin_device_user_fp",
        ),
    )
    op.create_index(
        "ix_admin_devices_user",
        "admin_devices",
        ["user_id"],
    )

    op.create_table(
        "admin_sessions",
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
            "jti",
            sa.String(64),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "device_id",
            sa.BigInteger,
            sa.ForeignKey(
                "admin_devices.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "refresh_jti",
            sa.String(64),
            nullable=True,
            unique=True,
        ),
        sa.Column(
            "ip",
            sa.String(64),
            nullable=True,
        ),
        sa.Column(
            "ua",
            sa.String(512),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_admin_sessions_user_active",
        "admin_sessions",
        ["user_id", "revoked_at"],
    )

    op.create_table(
        "admin_login_attempts",
        sa.Column(
            "id",
            sa.BigInteger,
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger,
            nullable=True,
        ),
        sa.Column(
            "ip",
            sa.String(64),
            nullable=True,
        ),
        sa.Column(
            "ua",
            sa.String(512),
            nullable=True,
        ),
        sa.Column(
            "success",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "reason",
            sa.String(64),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_admin_login_attempts_user_time",
        "admin_login_attempts",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_admin_login_attempts_ip_time",
        "admin_login_attempts",
        ["ip", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_admin_login_attempts_ip_time",
        table_name="admin_login_attempts",
    )
    op.drop_index(
        "ix_admin_login_attempts_user_time",
        table_name="admin_login_attempts",
    )
    op.drop_table("admin_login_attempts")

    op.drop_index(
        "ix_admin_sessions_user_active",
        table_name="admin_sessions",
    )
    op.drop_table("admin_sessions")

    op.drop_index(
        "ix_admin_devices_user",
        table_name="admin_devices",
    )
    op.drop_table("admin_devices")

    op.drop_column(
        "users", "admin_backup_codes_hash"
    )
    op.drop_column("users", "admin_totp_enabled")
    op.drop_column(
        "users", "admin_totp_secret_encrypted"
    )
    op.drop_column("users", "admin_init")
