"""repair invalid soundcloud track owners

Revision ID: 0017
Revises: 0016
Create Date: 2026-04-12
"""

from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    tracks = sa.table(
        "tracks",
        sa.column("id", sa.Integer()),
        sa.column("source", sa.String()),
        sa.column("uploaded_by_id", sa.BigInteger()),
        sa.column(
            "created_at", sa.DateTime(timezone=True)
        ),
    )
    users = sa.table(
        "users",
        sa.column("id", sa.BigInteger()),
        sa.column(
            "created_at", sa.DateTime(timezone=True)
        ),
    )

    invalid_track_ids = sa.select(tracks.c.id).select_from(
        tracks.outerjoin(
            users,
            tracks.c.uploaded_by_id == users.c.id,
        )
    ).where(
        tracks.c.source == "soundcloud",
        tracks.c.uploaded_by_id.is_not(None),
        sa.or_(
            users.c.id.is_(None),
            tracks.c.created_at < users.c.created_at,
        ),
    )

    bind.execute(
        sa.update(tracks)
        .where(tracks.c.id.in_(invalid_track_ids))
        .values(uploaded_by_id=None)
    )


def downgrade() -> None:
    pass
