"""Artist enrichment: pulls external artist metadata via PrivateCore.

PrivateCore is an opaque dependency; this service only sees the
`ArtistInfo` dataclass and `fetch_artist_info` coroutine. It must not
reference specific external providers, scraping libraries or model
names anywhere.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core import s3
from app.models.artist import Artist
from app.models.track import Track
from app.models.artist import TrackArtist

if TYPE_CHECKING:
    pass

logger = structlog.stdlib.get_logger(__name__)

_ALLOWED_IMAGE_MIMES = frozenset(
    {"image/jpeg", "image/png", "image/webp"}
)
_MAX_BIO_CHARS = 8000


class ArtistNotFound(Exception):
    pass


class ArtistEnrichmentService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enrich(self, artist_id: int) -> Artist:
        """Pull external metadata, persist, upload image to S3.

        Guarantees:
          - never raises on provider-side issues; sets enrichment_status='failed'.
          - uses SELECT FOR UPDATE SKIP LOCKED to avoid duplicate work.
          - updates enrichment_status + enriched_at on every terminal path.
        """
        artist = await self._lock_artist(artist_id)
        if artist is None:
            raise ArtistNotFound(str(artist_id))

        # Mark in-progress so concurrent triggers bail out early.
        artist.enrichment_status = "in_progress"
        await self._session.commit()

        hints = await self._collect_hints(artist)

        try:
            from dotsound_private_core.services.artist_info_provider import (  # noqa: E501
                fetch_artist_info,
            )

            info = await asyncio.wait_for(
                fetch_artist_info(
                    name=artist.name,
                    hints=hints,
                    timeout_seconds=settings.artist_enrichment_timeout_seconds,
                ),
                timeout=settings.artist_enrichment_timeout_seconds + 5,
            )
        except Exception:
            logger.exception(
                "artist_enrichment_error",
                artist_id=artist_id,
                stage="provider",
            )
            await self._finalize(artist, "failed")
            return artist

        if info is None or info.confidence < settings.artist_enrichment_min_confidence:
            logger.info(
                "artist_enrichment_not_found",
                artist_id=artist_id,
                confidence=getattr(info, "confidence", None),
            )
            await self._finalize(artist, "not_found")
            return artist

        # Save text fields first so that an image-download failure does
        # not wipe out usable data.
        if info.bio:
            artist.bio = info.bio[:_MAX_BIO_CHARS]
        if info.birth_date:
            artist.birth_date = info.birth_date
        if info.birthplace:
            artist.birthplace = info.birthplace[:128]
        if info.country:
            artist.country = info.country.upper()[:2]
        if info.website_url:
            artist.website_url = info.website_url[:512]

        if info.image_url:
            try:
                new_key = await self._download_and_store_image(
                    info.image_url
                )
                if new_key:
                    old_key = artist.image_key
                    artist.image_key = new_key
                    if old_key and old_key != new_key:
                        try:
                            await s3.delete_object(old_key)
                        except Exception:
                            logger.exception(
                                "artist_old_image_delete_failed",
                                artist_id=artist_id,
                                old_key=old_key,
                            )
            except Exception:
                logger.exception(
                    "artist_image_download_failed",
                    artist_id=artist_id,
                )

        await self._finalize(artist, "done")
        logger.info(
            "artist_enrichment_success",
            artist_id=artist_id,
            has_bio=bool(artist.bio),
            has_birth_date=bool(artist.birth_date),
            has_image=bool(artist.image_key),
        )
        return artist

    async def schedule_enrich(self, artist_id: int) -> None:
        """Fire-and-forget enqueue of the enrichment task."""
        try:
            from app.services.artist_enrichment_worker import (
                enrich_artist_task,
            )

            await enrich_artist_task.kiq(artist_id=artist_id)
        except Exception:
            logger.exception(
                "artist_enrich_schedule_failed",
                artist_id=artist_id,
            )

    async def get_pending(self, limit: int = 50) -> list[int]:
        result = await self._session.execute(
            select(Artist.id)
            .where(Artist.enrichment_status == "pending")
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _lock_artist(self, artist_id: int) -> Artist | None:
        stmt = select(Artist).where(Artist.id == artist_id)
        try:
            bind = self._session.get_bind()
            dialect_name = bind.dialect.name
        except Exception:
            dialect_name = ""
        if dialect_name in ("postgresql", "postgres"):
            stmt = stmt.with_for_update(skip_locked=True)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _finalize(
        self, artist: Artist, status_value: str
    ) -> None:
        artist.enrichment_status = status_value
        artist.enriched_at = datetime.now(timezone.utc)
        await self._session.commit()

    async def _collect_hints(self, artist: Artist) -> dict:
        hints: dict[str, str] = {}
        if artist.source and artist.source != "internal":
            hints["source_hint"] = artist.source

        result = await self._session.execute(
            select(Track.genre, func.count(Track.id))
            .join(
                TrackArtist,
                TrackArtist.track_id == Track.id,
            )
            .where(
                TrackArtist.artist_id == artist.id,
                Track.genre.is_not(None),
            )
            .group_by(Track.genre)
            .order_by(func.count(Track.id).desc())
            .limit(1)
        )
        row = result.first()
        if row and row[0]:
            hints["genre_hint"] = str(row[0])

        return hints

    async def _download_and_store_image(
        self, image_url: str
    ) -> str | None:
        async with httpx.AsyncClient(
            timeout=20.0, follow_redirects=True
        ) as client:
            resp = await client.get(image_url)
            resp.raise_for_status()

            content_type = (
                resp.headers.get("content-type", "")
                .split(";")[0]
                .strip()
                .lower()
            )
            if content_type not in _ALLOWED_IMAGE_MIMES:
                logger.info(
                    "artist_image_bad_content_type",
                    content_type=content_type,
                )
                return None

            data = resp.content
            if len(data) > settings.artist_image_max_bytes:
                logger.info(
                    "artist_image_too_large",
                    bytes=len(data),
                )
                return None

        img_key, _thumb_key, _w, _h = await s3.upload_image(
            data=data,
            prefix="artists",
            max_size=settings.image_avatar_max_size,
        )
        return img_key
