"""experiments + experiment_assignments tables.

Revision ID: 0093
Revises: 0092
Create Date: 2026-05-11
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0093"
down_revision = "0092"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "experiments",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "key",
            sa.String(length=64),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "description",
            sa.String(length=512),
            nullable=True,
        ),
        sa.Column("arms", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "is_holdout",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
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
    op.create_index("ix_experiments_status", "experiments", ["status"])
    op.create_table(
        "experiment_assignments",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "experiment_id",
            sa.Integer(),
            sa.ForeignKey("experiments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "arm",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "bucket",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_experiment_assignments_user",
        "experiment_assignments",
        ["user_id", "experiment_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_experiment_assignments_user",
        table_name="experiment_assignments",
    )
    op.drop_table("experiment_assignments")
    op.drop_index("ix_experiments_status", table_name="experiments")
    op.drop_table("experiments")
