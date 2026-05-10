"""track soft-delete columns + admin_actions_log user_id index

Adds three columns to ``tracks`` for the unified soft-delete /
restore lifecycle (owner UI, admin moderation, eventual hard
purge in cron):

* ``deleted_at``    -- timestamp the row entered "trash"; NULL means
                       row is alive. Hard-delete cron consumes this.
* ``deleted_by_id`` -- who initiated the soft-delete (owner or admin
                       capability). FK SET NULL so user hard-delete
                       does not cascade-wipe content history.
* ``deleted_reason``-- short opaque code (``owner``, ``admin``,
                       ``dmca``, ``auto``).

Existing ``is_active=False`` rows keep ``deleted_at = NULL`` so
they do NOT flow into the hard-delete pipeline (legacy hidden
tracks remain hidden, but never auto-purged).

Also seeds the ``daily-track-hard-delete`` scheduled job and
adds an index on ``admin_actions_log.user_id`` so the per-user
cleanup query in ``account_deletion_service`` is cheap (the
column has no FK by design -- audit log must outlive the
account row partially, until policy-driven retention kicks in).

Revision ID: 0087
Revises: 0086
Create Date: 2026-05-10
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0087"
down_revision = "0086"
branch_labels = None
depends_on = None

_TRACK_HARD_DELETE_JOB_ID = "daily-track-hard-delete"
_ADMIN_LOG_INDEX = "ix_admin_actions_log_user_id"


def upgrade() -> None:
    op.add_column(
        "tracks",
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "tracks",
        sa.Column(
            "deleted_by_id",
            sa.BigInteger(),
            nullable=True,
        ),
    )
    op.add_column(
        "tracks",
        sa.Column(
            "deleted_reason",
            sa.String(length=32),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "tracks_deleted_by_id_fkey",
        "tracks",
        "users",
        ["deleted_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_tracks_deleted_at",
        "tracks",
        ["deleted_at"],
    )

    op.create_index(
        _ADMIN_LOG_INDEX,
        "admin_actions_log",
        ["user_id"],
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
                "id": _TRACK_HARD_DELETE_JOB_ID,
                "name": "Hard-delete tracks past grace period",
                "task_name": (
                    "app.services."
                    "track_hard_delete_worker:"
                    "hard_delete_expired_tracks_task"
                ),
                "cron": "0 4 * * *",
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
        ).bindparams(sid=_TRACK_HARD_DELETE_JOB_ID)
    )

    op.drop_index(_ADMIN_LOG_INDEX, table_name="admin_actions_log")

    op.drop_index("ix_tracks_deleted_at", table_name="tracks")
    op.drop_constraint(
        "tracks_deleted_by_id_fkey",
        "tracks",
        type_="foreignkey",
    )
    op.drop_column("tracks", "deleted_reason")
    op.drop_column("tracks", "deleted_by_id")
    op.drop_column("tracks", "deleted_at")
