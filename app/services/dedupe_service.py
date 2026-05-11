"""Per-user upload deduplication by compound audio hash.

The hash is computed client-side over (head_4MiB + tail_4MiB +
total_size) to keep mobile devices responsive. Lookup is scoped to
``uploaded_by_id`` so users only ever see matches against their own
library (privacy).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track


class DedupeService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_for_user(
        self,
        *,
        user_id: int,
        audio_hash: str,
    ) -> Track | None:
        stmt = (
            select(Track)
            .where(
                Track.uploaded_by_id == user_id,
                Track.audio_hash == audio_hash,
                Track.is_active.is_(True),
            )
            .order_by(Track.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
