"""upload_sessions table for chunked uploads + tracks.audio_hash

Adds:

* ``upload_sessions`` -- stateful chunked-upload session backed by
  an S3 multipart upload. Tracks per-chunk completion, expiry and
  any client-supplied metadata so a partial upload can be resumed
  after network loss or app reload.
* ``tracks.audio_hash`` -- compound SHA-256 of head/tail bytes +
  total size, populated on completion of a v2 upload. Used to
  detect user-side duplicate uploads (scoped to ``uploaded_by_id``).
* Hourly ``upload-session-cleanup`` scheduled job that aborts
  orphaned multipart uploads after ``expires_at`` lapses.

Revision ID: 0095
Revises: 0094
Create Date: 2026-05-12
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0095"
down_revision = "0094"
branch_labels = None
depends_on = None

_CLEANUP_JOB_ID = "upload-session-cleanup"


def upgrade() -> None:
    op.add_column(
        "tracks",
        sa.Column("audio_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_tracks_user_audio_hash",
        "tracks",
        ["uploaded_by_id", "audio_hash"],
        postgresql_where=sa.text("audio_hash IS NOT NULL"),
        sqlite_where=sa.text("audio_hash IS NOT NULL"),
    )

    op.create_table(
        "upload_sessions",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "upload_id",
            sa.String(length=36),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("mime", sa.String(length=64), nullable=False),
        sa.Column("total_size", sa.BigInteger(), nullable=False),
        sa.Column("audio_hash", sa.String(length=64), nullable=True),
        sa.Column("chunk_size", sa.Integer(), nullable=False),
        sa.Column("expected_chunks", sa.Integer(), nullable=False),
        sa.Column(
            "completed_chunks",
            sa.JSON(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("s3_key", sa.Text(), nullable=False),
        sa.Column("s3_multipart_id", sa.Text(), nullable=True),
        sa.Column("s3_parts", sa.JSON(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="active",
        ),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column(
            "track_id",
            sa.Integer(),
            sa.ForeignKey("tracks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_upload_sessions_upload_id",
        "upload_sessions",
        ["upload_id"],
        unique=True,
    )
    op.create_index(
        "ix_upload_sessions_audio_hash",
        "upload_sessions",
        ["audio_hash"],
    )
    op.create_index(
        "ix_upload_sessions_user_status",
        "upload_sessions",
        ["user_id", "status"],
    )
    op.create_index(
        "ix_upload_sessions_expires_at",
        "upload_sessions",
        ["expires_at"],
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
                "id": _CLEANUP_JOB_ID,
                "name": (
                    "Abort orphan upload_sessions past expiry"
                ),
                "task_name": (
                    "app.services."
                    "upload_session_cleanup_worker:"
                    "cleanup_upload_sessions_task"
                ),
                "cron": "0 * * * *",
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
        ).bindparams(sid=_CLEANUP_JOB_ID)
    )
    op.drop_index(
        "ix_upload_sessions_expires_at",
        table_name="upload_sessions",
    )
    op.drop_index(
        "ix_upload_sessions_user_status",
        table_name="upload_sessions",
    )
    op.drop_index(
        "ix_upload_sessions_audio_hash",
        table_name="upload_sessions",
    )
    op.drop_index(
        "ix_upload_sessions_upload_id",
        table_name="upload_sessions",
    )
    op.drop_table("upload_sessions")
    op.drop_index(
        "ix_tracks_user_audio_hash",
        table_name="tracks",
    )
    op.drop_column("tracks", "audio_hash")
