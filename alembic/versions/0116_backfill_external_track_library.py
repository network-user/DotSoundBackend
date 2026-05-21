"""Backfill external track library links and clear false ownership.

External search/import rows are canonical shared references. Older code
stored the first importer in ``tracks.uploaded_by_id``, which made that
user look like the global owner of the shared track. Move that legacy
marker into ``user_track_library`` and clear ``uploaded_by_id`` for
``external_reference`` rows.

Revision ID: 0116
Revises: 0115
Create Date: 2026-05-21
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0116"
down_revision: str | None = "0115"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO user_track_library (
            user_id,
            track_id,
            source,
            imported_at
        )
        SELECT
            t.uploaded_by_id,
            t.id,
            COALESCE(
                NULLIF(t.imported_from, ''),
                NULLIF(t.source_platform, ''),
                NULLIF(t.source, ''),
                'external'
            ),
            COALESCE(t.created_at, CURRENT_TIMESTAMP)
        FROM tracks AS t
        WHERE t.catalog_type = 'external_reference'
          AND t.uploaded_by_id IS NOT NULL
        ON CONFLICT (user_id, track_id) DO UPDATE
        SET source = COALESCE(user_track_library.source, excluded.source)
        """
    )
    op.execute(
        """
        UPDATE tracks
        SET uploaded_by_id = NULL
        WHERE catalog_type = 'external_reference'
          AND uploaded_by_id IS NOT NULL
        """
    )


def downgrade() -> None:
    pass
