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
from datetime import UTC, datetime
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

_WIKI_THUMB_RE = re.compile(
    r"^https?://upload\.wikimedia\.org/wikipedia/"
    r"(?P<project>[^/]+)/thumb/[0-9a-f]/[0-9a-f]{2}/"
    r"(?P<filename>[^/]+)/(?P<width>\d+)px-"
)
_WIKI_FULL_RE = re.compile(
    r"^https?://upload\.wikimedia\.org/wikipedia/"
    r"(?P<project>[^/]+)/[0-9a-f]/[0-9a-f]{2}/"
    r"(?P<filename>[^/?#]+)$"
)


def _wikipedia_filepath_url(url: str) -> str | None:
    """Map upload.wikimedia.org/.../thumb/.../NNNpx-… to a stable
    Special:FilePath URL on commons.wikimedia.org. Returns None for
    non-Wikimedia URLs.
    """
    m = _WIKI_THUMB_RE.match(url)
    if m:
        project = m.group("project")
        filename = m.group("filename")
        width = m.group("width")
        host = (
            "commons.wikimedia.org"
            if project == "commons"
            else "en.wikipedia.org"
        )
        return (
            f"https://{host}/wiki/Special:FilePath/"
            f"{filename}?width={width}"
        )
    m = _WIKI_FULL_RE.match(url)
    if m:
        project = m.group("project")
        filename = m.group("filename")
        host = (
            "commons.wikimedia.org"
            if project == "commons"
            else "en.wikipedia.org"
        )
        return (
            f"https://{host}/wiki/Special:FilePath/{filename}"
        )
    return None


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
            except TimeoutError:
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
            await self._schedule_supplemental(artist_id)
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
            if conf is not None:
                artist.enrichment_confidence = float(conf)
            await self._finalize(artist, "not_found")
            await self._schedule_supplemental(artist_id)
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

        if not artist.discography_manual_lock:
            raw_discography = getattr(info, "discography", None)
            normalized_discography = _normalize_discography(
                raw_discography
            )
            if normalized_discography:
                artist.discography = normalized_discography

        raw_profiles = getattr(info, "source_profiles", None)
        normalized_profiles = _normalize_source_profiles(
            raw_profiles
        )
        if normalized_profiles:
            artist.source_profiles = normalized_profiles

        primary_id = getattr(info, "primary_source_id", None)
        if isinstance(primary_id, str) and primary_id:
            artist.primary_source_id = primary_id

        if info.image_url and not artist.image_key:
            await _log("saving", "downloading image")
            try:
                new_key = await self._download_and_store_image(
                    info.image_url
                )
            except Exception:
                logger.exception(
                    "artist_image_download_unexpected_error",
                    artist_id=artist_id,
                )
                new_key = None
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
            else:
                await _log(
                    "saving",
                    "image not available (keeping text)",
                )
        elif info.image_url and artist.image_key:
            await _log(
                "saving",
                "skipping image (artist already has image_key)",
            )

        artist.enrichment_confidence = float(info.confidence)
        await self._finalize(artist, "done")
        await _log("done", "saved to DB")
        await self._schedule_catalog_sync(artist_id)
        logger.info(
            "artist_enrichment_success",
            artist_id=artist_id,
            has_bio=bool(artist.bio),
            has_birth_date=bool(artist.birth_date),
            has_image=bool(artist.image_key),
        )
        return artist

    async def _schedule_supplemental(self, artist_id: int) -> None:
        try:
            from app.services.artist_supplemental_worker import (
                enrich_artist_supplemental_task,
            )

            await enrich_artist_supplemental_task.kiq(artist_id=artist_id)
        except Exception:
            logger.exception(
                "artist_supplemental_schedule_failed",
                artist_id=artist_id,
            )

    async def _schedule_catalog_sync(self, artist_id: int) -> None:
        try:
            from app.services import artist_catalog_sync_progress as acsp
            from app.services.artist_catalog_sync_worker import (
                sync_artist_catalog_task,
            )
            from app.services.background_jobs import enqueue

            try:
                await acsp.set_running(
                    artist_id,
                    mode="full",
                    soundcloud_album_id=None,
                    detail={
                        "phase": "queued",
                        "source": "artist_enrichment",
                    },
                )
            except Exception as exc:
                logger.warning(
                    "artist_catalog_auto_sync_progress_unavailable",
                    artist_id=artist_id,
                    error=str(exc),
                )
            await enqueue(
                sync_artist_catalog_task,
                payload={"artist_id": artist_id},
                idempotency_key=f"artist-catalog-sync:{artist_id}",
            )
        except Exception as exc:
            if exc.__class__.__name__ == "IdempotencySkipped":
                logger.info(
                    "artist_catalog_auto_sync_already_queued",
                    artist_id=artist_id,
                )
                return
            logger.exception(
                "artist_catalog_auto_sync_schedule_failed",
                artist_id=artist_id,
            )

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
        artist.enriched_at = datetime.now(UTC)
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
        data = await self._fetch_image_bytes(image_url)
        if data is None:
            return None
        img_key, _thumb_key, _w, _h = await s3.upload_image(
            data=data,
            prefix="artists",
            max_size=settings.image_avatar_max_size,
        )
        return img_key

    async def _fetch_image_bytes(
        self, image_url: str
    ) -> bytes | None:
        candidates = [image_url]
        fallback = _wikipedia_filepath_url(image_url)
        if fallback and fallback != image_url:
            candidates.append(fallback)

        headers = {
            "User-Agent": settings.outbound_user_agent,
            "Accept": (
                "image/webp,image/jpeg,image/png,"
                "image/*;q=0.8,*/*;q=0.5"
            ),
            "Accept-Language": "en;q=0.9, *;q=0.5",
        }
        if settings.outbound_contact_email:
            headers["From"] = settings.outbound_contact_email

        async with httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
            headers=headers,
        ) as client:
            for url in candidates:
                data = await self._try_one(client, url)
                if data is not None:
                    return data
        return None

    async def _try_one(
        self,
        client: httpx.AsyncClient,
        url: str,
    ) -> bytes | None:
        try:
            resp = await client.get(url)
        except httpx.HTTPError as exc:
            logger.warning(
                "artist_image_download_network_error",
                url=url,
                error=str(exc),
            )
            return None

        if resp.status_code in (403, 404, 410, 429):
            logger.warning(
                "artist_image_download_rejected",
                url=url,
                status=resp.status_code,
            )
            return None
        if resp.status_code >= 400:
            logger.warning(
                "artist_image_download_failed_status",
                url=url,
                status=resp.status_code,
            )
            return None

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
                url=url,
            )
            return None

        data = resp.content
        if len(data) > settings.artist_image_max_bytes:
            logger.info(
                "artist_image_too_large",
                bytes=len(data),
                url=url,
            )
            return None
        return data


_MAX_DISCOGRAPHY_ITEMS = 60
_MAX_SOURCE_PROFILES = 6
_MAX_PROFILE_BIO_CHARS = 4000
_ALLOWED_URL_SCHEMES = ("http://", "https://")


def _safe_str(value: object, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    return text[:limit]


def _safe_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if not text.startswith(_ALLOWED_URL_SCHEMES):
        return None
    return text[:1024]


def _safe_int(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _safe_iso_date(value: object) -> str | None:
    if value is None:
        return None
    iso = getattr(value, "isoformat", None)
    if callable(iso):
        try:
            text = iso()
        except Exception:
            return None
        if isinstance(text, str):
            return text[:32]
    if isinstance(value, str):
        return value.strip()[:32] or None
    return None


def _normalize_discography(raw: object) -> list[dict] | None:
    if not isinstance(raw, (list, tuple)):
        return None
    out: list[dict] = []
    for item in raw:
        title: str | None = None
        year: int | None = None
        type_: str | None = None
        url: str | None = None
        if isinstance(item, dict):
            title = _safe_str(item.get("title"), 256)
            year = _safe_int(item.get("year"))
            type_ = _safe_str(item.get("type"), 64)
            url = _safe_url(item.get("url"))
        else:
            title = _safe_str(getattr(item, "title", None), 256)
            year = _safe_int(getattr(item, "year", None))
            type_ = _safe_str(getattr(item, "type", None), 64)
            url = _safe_url(getattr(item, "url", None))
        if not title:
            continue
        entry: dict[str, object] = {"title": title}
        if year is not None:
            entry["year"] = year
        if type_:
            entry["type"] = type_
        if url:
            entry["url"] = url
        out.append(entry)
        if len(out) >= _MAX_DISCOGRAPHY_ITEMS:
            break
    return out or None


def _normalize_source_profiles(raw: object) -> list[dict] | None:
    if not isinstance(raw, (list, tuple)):
        return None
    out: list[dict] = []
    for item in raw:
        if isinstance(item, dict):
            getter = item.get
        else:
            def getter(key: str, _o: object = item) -> object:
                return getattr(_o, key, None)
        source_id = _safe_str(getter("source_id"), 32)
        if not source_id:
            continue
        source_name = (
            _safe_str(getter("source_name"), 64) or source_id
        )
        entry: dict[str, object] = {
            "source_id": source_id,
            "source_name": source_name,
        }
        url = _safe_url(getter("source_page_url"))
        if url:
            entry["source_page_url"] = url
        bio = _safe_str(getter("bio"), _MAX_PROFILE_BIO_CHARS)
        if bio:
            entry["bio"] = bio
        birth_date = _safe_iso_date(getter("birth_date"))
        if birth_date:
            entry["birth_date"] = birth_date
        birthplace = _safe_str(getter("birthplace"), 128)
        if birthplace:
            entry["birthplace"] = birthplace
        country = _safe_str(getter("country"), 8)
        if country:
            entry["country"] = country.upper()[:2]
        image_url = _safe_url(getter("image_url"))
        if image_url:
            entry["image_url"] = image_url
        website_url = _safe_url(getter("website_url"))
        if website_url:
            entry["website_url"] = website_url
        discography = _normalize_discography(
            getter("discography")
        )
        if discography:
            entry["discography"] = discography
        out.append(entry)
        if len(out) >= _MAX_SOURCE_PROFILES:
            break
    return out or None
