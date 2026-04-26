"""generic compute_jobs queue

Revision ID: 0057
Revises: 0056
Create Date: 2026-04-26
"""

import sqlalchemy as sa
from alembic import op

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "compute_jobs",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("job_type", sa.String(48), nullable=False),
        sa.Column("target_kind", sa.String(24), nullable=True),
        sa.Column("target_id", sa.String(64), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column(
            "feature_version",
            sa.String(32),
            nullable=False,
            server_default="v1",
        ),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
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
            server_default="5",
        ),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("claimed_by", sa.String(32), nullable=True),
        sa.Column(
            "claimed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "claim_deadline_at",
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
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "job_type",
            "target_kind",
            "target_id",
            "feature_version",
            name="uq_compute_job_target",
        ),
    )
    op.create_index(
        "ix_compute_jobs_claim",
        "compute_jobs",
        ["status", "priority", "next_attempt_at"],
    )
    op.create_index(
        "ix_compute_jobs_type_status",
        "compute_jobs",
        ["job_type", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_compute_jobs_type_status", "compute_jobs")
    op.drop_index("ix_compute_jobs_claim", "compute_jobs")
    op.drop_table("compute_jobs")
