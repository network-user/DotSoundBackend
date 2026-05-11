"""Upload deduplication.

Two cooperating layers:

* **Per-user compound-hash pre-check** — fast head+tail+size hash
  computed on the client. Lookup is scoped to ``uploaded_by_id`` so
  users only ever see matches against their own library (privacy /
  UX: "this is already in your library").
* **Cross-user source-SHA-256 dedup at finalize** — computed
  server-side from the assembled multipart object and resolved
  through :class:`app.services.audio_blob_service.AudioBlobService`
  to short-circuit the transcode pipeline when the source has been
  ingested before by anyone.

Cross-user matches are never surfaced to the client; we just attach
the existing AudioBlob transparently.
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

    async def find_for_user_by_source(
        self,
        *,
        user_id: int,
        source_sha256: str,
    ) -> Track | None:
        """Server-authoritative dedup lookup for the current user."""
        stmt = (
            select(Track)
            .where(
                Track.uploaded_by_id == user_id,
                Track.source_sha256 == source_sha256,
                Track.is_active.is_(True),
            )
            .order_by(Track.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
