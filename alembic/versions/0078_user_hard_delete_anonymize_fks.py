"""user hard delete: anonymize-friendly FKs + scheduled job

Switch ``messages.sender_id`` and ``track_comments.user_id`` from
``ON DELETE CASCADE`` to ``ON DELETE SET NULL`` so that hard-deleting
a user during the GDPR/152-FZ retention sweep preserves the message
or comment history of *other* participants. The deleted user's
identity is rendered opaque on the read path (``Deleted user``).

Also seeds a daily ``hard_delete_expired_users`` cron entry into
``scheduled_jobs`` (runs at 03:30 UTC every day).

Revision ID: 0078
Revises: 0077
Create Date: 2026-05-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0078"
down_revision = "0077"
branch_labels = None
depends_on = None

_SCHEDULED_JOB_ID = "daily-user-hard-delete"

_FK_TARGETS: tuple[tuple[str, str, str], ...] = (
    ("messages", "sender_id", "messages_sender_id_fkey"),
    ("track_comments", "user_id", "track_comments_user_id_fkey"),
)


def upgrade() -> None:
    op.alter_column(
        "messages",
        "sender_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )
    op.alter_column(
        "track_comments",
        "user_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )

    for table, column, name in _FK_TARGETS:
        op.drop_constraint(name, table, type_="foreignkey")
        op.create_foreign_key(
            name,
            table,
            "users",
            [column],
            ["id"],
            ondelete="SET NULL",
        )

    jobs_table = sa.table(
        "scheduled_jobs",
        sa.column("id", sa.String),
        sa.column("name", sa.String),
        sa.column("task_name", sa.String),
        sa.column("cron", sa.String),
        sa.column("queue", sa.String),
        sa.column("payload", sa.JSON),
        sa.column("enabled", sa.Boolean),
    )
    op.bulk_insert(
        jobs_table,
        [
            {
                "id": _SCHEDULED_JOB_ID,
                "name": "Hard-delete users past grace period",
                "task_name": (
                    "app.services.account_deletion_worker:"
                    "hard_delete_expired_users_task"
                ),
                "cron": "30 3 * * *",
                "queue": "default",
                "payload": {},
                "enabled": True,
            }
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM scheduled_jobs WHERE id = :sid"
        ).bindparams(sid=_SCHEDULED_JOB_ID)
    )

    for table, column, name in _FK_TARGETS:
        op.execute(
            sa.text(
                f"UPDATE {table} SET {column} = 0 WHERE {column} IS NULL"
            )
        )
        op.drop_constraint(name, table, type_="foreignkey")
        op.create_foreign_key(
            name,
            table,
            "users",
            [column],
            ["id"],
            ondelete="CASCADE",
        )

    op.alter_column(
        "messages",
        "sender_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    op.alter_column(
        "track_comments",
        "user_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
