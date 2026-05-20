"""Add missing FK indexes and convert playback_suppressed_until to partial.

PostgreSQL does not auto-create indexes on foreign keys, so any WHERE /
JOIN that filters by a nullable FK without a dedicated index causes a
sequential scan once the table grows. Audit pass found these
unindexed FKs:

* ``messages.reply_to_id`` — used to fetch a thread's reply chain.
* ``messages.shared_track_id`` / ``shared_album_id`` /
  ``shared_playlist_id`` — used to look up which conversations
  shared a given asset (e.g. on the share-target picker).
* ``track_comments.user_id`` — used by per-user comment lists.
* ``track_comments.parent_id`` — used by comment tree expansion.
* ``co_listen_rooms.host_id`` / ``dj_id`` / ``track_id`` — used by
  room listing / "rooms playing this track" lookups.

Separately, ``tracks.playback_suppressed_until`` had a full B-tree
index, but the only predicate that uses it always combines
``IS NULL OR <= now()`` — the full index never helps the NULL branch
and wastes space on the majority NULL rows. Replace it with a partial
index on rows where the column is non-null, which is what the
"currently suppressed" branch actually scans.

Revision ID: 0114
Revises: 0113
Create Date: 2026-05-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0114"
down_revision: str | None = "0113"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_messages_reply_to_id",
        "messages",
        ["reply_to_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_messages_shared_track_id",
        "messages",
        ["shared_track_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_messages_shared_album_id",
        "messages",
        ["shared_album_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_messages_shared_playlist_id",
        "messages",
        ["shared_playlist_id"],
        if_not_exists=True,
    )

    op.create_index(
        "ix_track_comments_user_id",
        "track_comments",
        ["user_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_track_comments_parent_id",
        "track_comments",
        ["parent_id"],
        if_not_exists=True,
    )

    op.create_index(
        "ix_co_listen_rooms_host_id",
        "co_listen_rooms",
        ["host_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_co_listen_rooms_dj_id",
        "co_listen_rooms",
        ["dj_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_co_listen_rooms_track_id",
        "co_listen_rooms",
        ["track_id"],
        if_not_exists=True,
    )

    op.drop_index(
        "ix_tracks_playback_suppressed_until",
        table_name="tracks",
        if_exists=True,
    )
    op.create_index(
        "ix_tracks_playback_suppressed_until_partial",
        "tracks",
        ["playback_suppressed_until"],
        postgresql_where=sa.text(
            "playback_suppressed_until IS NOT NULL"
        ),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tracks_playback_suppressed_until_partial",
        table_name="tracks",
        if_exists=True,
    )
    op.create_index(
        "ix_tracks_playback_suppressed_until",
        "tracks",
        ["playback_suppressed_until"],
        if_not_exists=True,
    )

    op.drop_index(
        "ix_co_listen_rooms_track_id",
        table_name="co_listen_rooms",
        if_exists=True,
    )
    op.drop_index(
        "ix_co_listen_rooms_dj_id",
        table_name="co_listen_rooms",
        if_exists=True,
    )
    op.drop_index(
        "ix_co_listen_rooms_host_id",
        table_name="co_listen_rooms",
        if_exists=True,
    )

    op.drop_index(
        "ix_track_comments_parent_id",
        table_name="track_comments",
        if_exists=True,
    )
    op.drop_index(
        "ix_track_comments_user_id",
        table_name="track_comments",
        if_exists=True,
    )

    op.drop_index(
        "ix_messages_shared_playlist_id",
        table_name="messages",
        if_exists=True,
    )
    op.drop_index(
        "ix_messages_shared_album_id",
        table_name="messages",
        if_exists=True,
    )
    op.drop_index(
        "ix_messages_shared_track_id",
        table_name="messages",
        if_exists=True,
    )
    op.drop_index(
        "ix_messages_reply_to_id",
        table_name="messages",
        if_exists=True,
    )
