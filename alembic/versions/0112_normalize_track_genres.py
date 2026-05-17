"""Normalize track genre values to lowercase-trimmed form.

Converts all existing genre values to LOWER(TRIM(genre)) to deduplicate
variants like "Hip-Hop" / "hip-hop" / "Hip Hop" into a single canonical
key. After this migration, genres from the DB arrive pre-normalized so the
onboarding bubble list no longer splits the same genre into multiple entries.

Revision ID: 0112
Revises: 0111
Create Date: 2026-05-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0112"
down_revision: str | None = "0111"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE tracks"
            " SET genre = LOWER(TRIM(genre))"
            " WHERE genre IS NOT NULL AND genre != ''"
        )
    )


def downgrade() -> None:
    pass
