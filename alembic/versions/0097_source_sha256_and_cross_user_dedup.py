"""Source-hash CAS, cross-user dedup, HLS bundle on AudioBlob.

Schema changes for transparent cross-user content-addressed storage:

* ``audio_blobs.source_sha256`` — SHA-256 of the *original* uploaded
  file (before transcode). Indexed unique, partial on NOT NULL so
  legacy rows without a source hash are tolerated. Allows looking up
  an already-known source and skipping the transcode pipeline on a
  re-upload by any user.
* ``audio_blobs.hls_manifest_key`` — master playlist key for the
  shared HLS bundle keyed by ``source_sha256``. Set once per source;
  reused across every Track that links to the blob.
* ``tracks.source_sha256`` — claim on a source; allows post-transcode
  hooks to attach the resulting AudioBlob to every Track waiting on
  the same source, even when uploads race.
* ``upload_sessions.source_sha256`` — populated at ``/complete`` after
  streaming SHA-256 from the assembled multipart object.
* Drop ``uq_tracks_user_blob_active`` — one user may now own multiple
  active Tracks referencing the same AudioBlob (e.g. duplicate entries
  in different playlists), and any number of users share the same blob.

Revision ID: 0097
Revises: 0096
Create Date: 2026-05-12
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0097"
down_revision = "0096"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audio_blobs",
        sa.Column("source_sha256", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "audio_blobs",
        sa.Column("hls_manifest_key", sa.Text(), nullable=True),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_audio_blobs_source_sha256 "
        "ON audio_blobs (source_sha256) "
        "WHERE source_sha256 IS NOT NULL"
    )

    op.add_column(
        "tracks",
        sa.Column("source_sha256", sa.String(length=64), nullable=True),
    )
    op.execute(
        "CREATE INDEX ix_tracks_source_sha256_pending "
        "ON tracks (source_sha256) "
        "WHERE source_sha256 IS NOT NULL AND blob_id IS NULL"
    )

    op.add_column(
        "upload_sessions",
        sa.Column("source_sha256", sa.String(length=64), nullable=True),
    )

    op.execute("DROP INDEX IF EXISTS uq_tracks_user_blob_active")


def downgrade() -> None:
    bind = op.get_bind()
    where = (
        "blob_id IS NOT NULL AND is_active = 1"
        if bind.dialect.name == "sqlite"
        else "blob_id IS NOT NULL AND is_active IS TRUE"
    )
    op.execute(
        f"CREATE UNIQUE INDEX uq_tracks_user_blob_active "
        f"ON tracks (uploaded_by_id, blob_id) WHERE ({where})"
    )

    op.drop_column("upload_sessions", "source_sha256")

    op.execute("DROP INDEX IF EXISTS ix_tracks_source_sha256_pending")
    op.drop_column("tracks", "source_sha256")

    op.execute("DROP INDEX IF EXISTS uq_audio_blobs_source_sha256")
    op.drop_column("audio_blobs", "hls_manifest_key")
    op.drop_column("audio_blobs", "source_sha256")
