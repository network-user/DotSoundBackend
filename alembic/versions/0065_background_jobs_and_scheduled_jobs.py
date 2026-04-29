"""background_jobs + scheduled_jobs unified task layer

Revision ID: 0065
Revises: 0064
Create Date: 2026-04-29
"""

import sqlalchemy as sa

from alembic import op

revision = "0065"
down_revision = "0064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "background_jobs",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("name", sa.String(96), nullable=False),
        sa.Column(
            "queue",
            sa.String(32),
            nullable=False,
            server_default="default",
        ),
        sa.Column(
            "status",
            sa.String(24),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "max_attempts",
            sa.Integer(),
            nullable=False,
            server_default="3",
        ),
        sa.Column(
            "scheduled_at",
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
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("result_summary", sa.JSON(), nullable=True),
        sa.Column("parent_job_id", sa.String(40), nullable=True),
        sa.Column(
            "scheduled_job_id", sa.String(40), nullable=True
        ),
        sa.Column(
            "created_by_user_id", sa.BigInteger(), nullable=True
        ),
        sa.Column(
            "idempotency_key", sa.String(128), nullable=True
        ),
        sa.Column("taskiq_task_id", sa.String(64), nullable=True),
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
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_background_jobs_idempotency_key",
        ),
    )
    op.create_index(
        "ix_background_jobs_status_created",
        "background_jobs",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_background_jobs_name",
        "background_jobs",
        ["name"],
    )
    op.create_index(
        "ix_background_jobs_queue",
        "background_jobs",
        ["queue"],
    )
    op.create_index(
        "ix_background_jobs_scheduled_job_id",
        "background_jobs",
        ["scheduled_job_id"],
    )
    op.create_index(
        "ix_background_jobs_parent_job_id",
        "background_jobs",
        ["parent_job_id"],
    )

    op.create_table(
        "scheduled_jobs",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column(
            "name", sa.String(96), nullable=False, unique=True
        ),
        sa.Column("task_name", sa.String(96), nullable=False),
        sa.Column(
            "queue",
            sa.String(32),
            nullable=False,
            server_default="default",
        ),
        sa.Column("cron", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "last_run_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "next_run_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("last_status", sa.String(24), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_job_id", sa.String(40), nullable=True),
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
    op.create_index(
        "ix_scheduled_jobs_enabled_next_run",
        "scheduled_jobs",
        ["enabled", "next_run_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_scheduled_jobs_enabled_next_run",
        table_name="scheduled_jobs",
    )
    op.drop_table("scheduled_jobs")

    op.drop_index(
        "ix_background_jobs_parent_job_id",
        table_name="background_jobs",
    )
    op.drop_index(
        "ix_background_jobs_scheduled_job_id",
        table_name="background_jobs",
    )
    op.drop_index(
        "ix_background_jobs_queue",
        table_name="background_jobs",
    )
    op.drop_index(
        "ix_background_jobs_name",
        table_name="background_jobs",
    )
    op.drop_index(
        "ix_background_jobs_status_created",
        table_name="background_jobs",
    )
    op.drop_table("background_jobs")
