"""lyrics cascade fields and worker security/scope fields

Revision ID: 0044
Revises: 0043
Create Date: 2026-04-22

Adds tier-cascade tracking to lyrics_jobs and security/scope
fields to compute_workers as part of the cascade-asr-offload
foundation work. One migration covers both because the new
worker columns are referenced by the cascade dispatcher.
"""

from alembic import op
import sqlalchemy as sa


revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lyrics_jobs",
        sa.Column(
            "tiers_planned",
            sa.JSON(),
            nullable=True,
        ),
    )
    op.add_column(
        "lyrics_jobs",
        sa.Column(
            "tier_attempts",
            sa.JSON(),
            nullable=True,
        ),
    )
    op.add_column(
        "lyrics_jobs",
        sa.Column(
            "current_tier",
            sa.String(32),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_lyrics_jobs_current_tier",
        "lyrics_jobs",
        ["current_tier"],
    )

    op.add_column(
        "compute_workers",
        sa.Column(
            "allowed_ip_cidrs",
            sa.JSON(),
            nullable=True,
        ),
    )
    op.add_column(
        "compute_workers",
        sa.Column(
            "allowed_profiles",
            sa.JSON(),
            nullable=True,
        ),
    )
    op.add_column(
        "compute_workers",
        sa.Column(
            "max_concurrent_jobs",
            sa.Integer,
            nullable=False,
            server_default="1",
        ),
    )
    op.add_column(
        "compute_workers",
        sa.Column(
            "suspended_until",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "compute_workers",
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_compute_workers_revoked_at",
        "compute_workers",
        ["revoked_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_compute_workers_revoked_at",
        table_name="compute_workers",
    )
    op.drop_column("compute_workers", "revoked_at")
    op.drop_column("compute_workers", "suspended_until")
    op.drop_column("compute_workers", "max_concurrent_jobs")
    op.drop_column("compute_workers", "allowed_profiles")
    op.drop_column("compute_workers", "allowed_ip_cidrs")

    op.drop_index(
        "ix_lyrics_jobs_current_tier",
        table_name="lyrics_jobs",
    )
    op.drop_column("lyrics_jobs", "current_tier")
    op.drop_column("lyrics_jobs", "tier_attempts")
    op.drop_column("lyrics_jobs", "tiers_planned")
