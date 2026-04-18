"""audio-compute worker infra

Revision ID: 0034
Revises: 0033
Create Date: 2026-04-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "compute_workers",
        sa.Column(
            "id", sa.String(32), primary_key=True
        ),
        sa.Column(
            "name", sa.String(128), nullable=False
        ),
        sa.Column(
            "profile",
            sa.String(32),
            nullable=False,
            server_default="cpu_light",
        ),
        sa.Column(
            "token_hash", sa.String(128), nullable=False
        ),
        sa.Column(
            "active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "suspended_reason",
            sa.String(64),
            nullable=True,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_ip", sa.String(64), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_compute_workers_profile_active",
        "compute_workers",
        ["profile", "active"],
    )

    op.create_table(
        "lyrics_jobs",
        sa.Column(
            "id", sa.String(40), primary_key=True
        ),
        sa.Column(
            "track_id",
            sa.BigInteger,
            sa.ForeignKey(
                "tracks.id", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column(
            "progress_id",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "requested_by_user_id",
            sa.BigInteger,
            nullable=True,
        ),
        sa.Column(
            "profile",
            sa.String(32),
            nullable=False,
            server_default="cpu_light",
        ),
        sa.Column(
            "status",
            sa.String(24),
            nullable=False,
            server_default="queued",
        ),
        sa.Column(
            "routed_to_worker",
            sa.String(32),
            nullable=True,
        ),
        sa.Column(
            "attempts",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "audio_sha256",
            sa.String(64),
            nullable=True,
        ),
        sa.Column(
            "error", sa.Text, nullable=True
        ),
        sa.Column(
            "deadline_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "finished_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "duration_ms", sa.Integer, nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_lyrics_jobs_status_profile",
        "lyrics_jobs",
        ["status", "profile"],
    )
    op.create_index(
        "ix_lyrics_jobs_progress_id",
        "lyrics_jobs",
        ["progress_id"],
    )

    op.create_table(
        "worker_audit_log",
        sa.Column(
            "id",
            sa.BigInteger,
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "worker_id", sa.String(32), nullable=True
        ),
        sa.Column(
            "ip", sa.String(64), nullable=True
        ),
        sa.Column(
            "action", sa.String(64), nullable=False
        ),
        sa.Column(
            "job_id", sa.String(40), nullable=True
        ),
        sa.Column(
            "status_code", sa.Integer, nullable=True
        ),
        sa.Column(
            "meta",
            sa.JSON(),
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
        "ix_worker_audit_log_created_at",
        "worker_audit_log",
        ["created_at"],
    )
    op.create_index(
        "ix_worker_audit_log_worker_id",
        "worker_audit_log",
        ["worker_id"],
    )

    op.create_table(
        "app_settings",
        sa.Column(
            "key", sa.String(96), primary_key=True
        ),
        sa.Column(
            "value", sa.JSON(), nullable=False
        ),
        sa.Column(
            "updated_by",
            sa.BigInteger,
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
    op.drop_index(
        "ix_worker_audit_log_worker_id",
        table_name="worker_audit_log",
    )
    op.drop_index(
        "ix_worker_audit_log_created_at",
        table_name="worker_audit_log",
    )
    op.drop_table("worker_audit_log")
    op.drop_index(
        "ix_lyrics_jobs_progress_id",
        table_name="lyrics_jobs",
    )
    op.drop_index(
        "ix_lyrics_jobs_status_profile",
        table_name="lyrics_jobs",
    )
    op.drop_table("lyrics_jobs")
    op.drop_index(
        "ix_compute_workers_profile_active",
        table_name="compute_workers",
    )
    op.drop_table("compute_workers")
