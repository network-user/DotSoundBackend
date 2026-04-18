"""Artist enrichment: pulls external artist metadata via PrivateCore.

PrivateCore is an opaque dependency; this service only sees the
`ArtistInfo` dataclass and `fetch_artist_info` coroutine. It must not
reference specific external providers, scraping libraries or model
names anywhere.
"""

from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core import s3
from app.models.artist import Artist, TrackArtist
from app.models.track import Track
from app.services import artist_enrichment_progress as progress

if TYPE_CHECKING:
    pass

logger = structlog.stdlib.get_logger(__name__)

_ALLOWED_IMAGE_MIMES = frozenset(
    {"image/jpeg", "image/png", "image/webp"}
)
_MAX_BIO_CHARS = 8000

_ARTIST_STAGE_LABELS: dict[str, str] = {
    "searching": "searching external sources",
    "fetching_details": "fetching artist detail pages",
    "merging": "merging results from sources",
    "saving": "saving to database",
}

_WIKITEXT_TEMPLATE = re.compile(r"\{\{[^}]*\}\}")
_WIKILINK_ALIAS = re.compile(r"\[\[(?:[^\]|]+)\|([^\]]+)\]\]")
_WIKILINK_PLAIN = re.compile(r"\[\[([^\]]+)\]\]")
_WIKI_JUNK = re.compile(r"[{}\[\]|]")


def _strip_wiki_markup(text: str) -> str:
    text = _WIKITEXT_TEMPLATE.sub("", text)
    text = _WIKILINK_ALIAS.sub(r"\1", text)
    text = _WIKILINK_PLAIN.sub(r"\1", text)
    text = _WIKI_JUNK.sub("", text)
    return " ".join(text.split()).strip()


async def _heartbeat_loop(
    progress_id: str,
    t0: float,
    stop_event: asyncio.Event,
    log_fn,
    interval: float = 5.0,
) -> None:
    try:
        while True:
            try:
                await asyncio.wait_for(
                    stop_event.wait(), timeout=interval
                )
                break
            except asyncio.TimeoutError:
                pass
            elapsed = f"{time.monotonic() - t0:.1f}s"
            await log_fn(
                "processing",
                f"\u23f3 still processing... (provider running, {elapsed} elapsed)",
            )
    except asyncio.CancelledError:
        pass


class ArtistNotFound(Exception):
    pass


class ArtistEnrichmentService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enrich(
        self,
        artist_id: int,
        bypass_cache: bool = False,
        progress_id: str | None = None,
    ) -> Artist:
        """Pull external metadata, persist, upload image to S3.

        When ``bypass_cache`` is True, the provider is asked to skip any
        internal cache and re-query sources — used by the manual admin
        "re-identify" button.

        When ``progress_id`` is supplied, stage labels and a short log
        are written to Redis so the UI can poll the debug panel.

        Guarantees:
          - never raises on provider-side issues; sets enrichment_status='failed'.
          - uses SELECT FOR UPDATE SKIP LOCKED to avoid duplicate work.
          - updates enrichment_status + enriched_at on every terminal path.
        """
        t0 = time.monotonic()

        async def _log(stage: str, msg: str) -> None:
            if not progress_id:
                return
            line = f"[{time.monotonic() - t0:.1f}s] {msg}"
            await progress.set_progress(
                progress_id,
                progress.opaque_stage(stage),
                line,
            )

        artist = await self._lock_artist(artist_id)
        if artist is None:
            await _log("error", "artist not found")
            raise ArtistNotFound(str(artist_id))

        await _log("queued", f"artist: {artist.name!r}")

        # Mark in-progress so concurrent triggers bail out early.
        artist.enrichment_status = "in_progress"
        await self._session.commit()

        hints = await self._collect_hints(artist)
        await _log(
            "searching",
            f"hints={hints or '{}'}; calling provider",
        )

        loop = asyncio.get_running_loop()

        def _on_progress(stage: str) -> None:
            if not progress_id:
                return
            label = _ARTIST_STAGE_LABELS.get(stage, "")
            desc = f" — {label}" if label else ""
            asyncio.run_coroutine_threadsafe(
                _log(stage, f"stage: {stage}{desc}"),
                loop,
            )

        try:
            from dotsound_private_core.services.artist_info_provider import (  # noqa: E501
                fetch_artist_info,
            )

            _stop_evt = asyncio.Event()
            _hb_task: asyncio.Task | None = None
            if progress_id:
                _hb_task = asyncio.create_task(
                    _heartbeat_loop(progress_id, t0, _stop_evt, _log)
                )
            try:
                info = await asyncio.wait_for(
                    asyncio.to_thread(
                        fetch_artist_info,
                        name=artist.name,
                        hints=hints,
                        timeout_seconds=settings.artist_enrichment_timeout_seconds,
                        bypass_cache=bypass_cache,
                        on_progress=_on_progress,
                    ),
                    timeout=settings.artist_enrichment_timeout_seconds + 5,
                )
            finally:
                _stop_evt.set()
                if _hb_task is not None:
                    _hb_task.cancel()
        except Exception as exc:
            logger.exception(
                "artist_enrichment_error",
                artist_id=artist_id,
                stage="provider",
            )
            await _log("error", f"provider error: {exc}")
            await self._finalize(artist, "failed")
            return artist

        if info is None or info.confidence < settings.artist_enrichment_min_confidence:
            logger.info(
                "artist_enrichment_not_found",
                artist_id=artist_id,
                confidence=getattr(info, "confidence", None),
            )
            conf = getattr(info, "confidence", None)
            await _log(
                "not_found",
                f"no reliable match (confidence={conf})",
            )
            await self._finalize(artist, "not_found")
            return artist

        await _log(
            "saving",
            (
                f"match confidence={info.confidence:.2f}; "
                f"bio={'Y' if info.bio else 'N'} "
                f"birth={'Y' if info.birth_date else 'N'} "
                f"place={'Y' if info.birthplace else 'N'} "
                f"image={'Y' if info.image_url else 'N'}"
            ),
        )

        # Save text fields first so that an image-download failure does
        # not wipe out usable data.
        if info.bio:
            artist.bio = info.bio[:_MAX_BIO_CHARS]
        if info.birth_date:
            artist.birth_date = info.birth_date
        if info.birthplace:
            artist.birthplace = _strip_wiki_markup(info.birthplace)[:128]
        if info.country:
            artist.country = info.country.upper()[:2]
        if info.website_url:
            artist.website_url = info.website_url[:512]

        raw_discography = getattr(info, "discography", None)
        if raw_discography and isinstance(raw_discography, list):
            artist.discography = raw_discography

        if info.image_url:
            await _log("saving", "downloading image")
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
                await _log(
                    "saving",
                    "image download failed (keeping text)",
                )

        await self._finalize(artist, "done")
        await _log("done", "saved to DB")
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
