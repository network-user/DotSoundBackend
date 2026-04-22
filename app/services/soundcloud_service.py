import httpx
import structlog
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core import s3
from app.models.track import Track
from app.services.sc_semaphore import (
    SoundCloudSemaphoreTimeout,
    soundcloud_slot,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_SC_API_BASE = "https://api-v2.soundcloud.com"
_SC_OEMBED_URL = "https://soundcloud.com/oembed"


class SoundCloudService:
    def __init__(self, client_id: str, session: AsyncSession) -> None:
        self._client_id = client_id
        self._session = session

    async def search(self, query: str, limit: int = 20) -> list[dict]:
        if not self._client_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SoundCloud search is not configured",
            )
        try:
            async with (
                soundcloud_slot(
                    timeout_seconds=(
                        settings.soundcloud_slot_acquire_timeout_seconds
                    ),
                ),
                httpx.AsyncClient(timeout=10) as client,
            ):
                r = await client.get(
                    f"{_SC_API_BASE}/search",
                    params={
                        "q": query,
                        "facet": "model",
                        "client_id": self._client_id,
                        "limit": limit,
                        "offset": 0,
                        "linked_partitioning": 1,
                    },
                )
                if r.status_code == 401:
                    raise HTTPException(
                        status_code=(status.HTTP_503_SERVICE_UNAVAILABLE),
                        detail=(
                            "SoundCloud client_id expired, "
                            "update SC_CLIENT_ID"
                        ),
                    )
                r.raise_for_status()
                data = r.json()
        except SoundCloudSemaphoreTimeout as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SoundCloud is busy, retry later",
            ) from exc
        tracks = [
            item
            for item in data.get("collection", [])
            if item.get("kind") == "track" and item.get("streamable")
        ]
        logger.info("sc_search_done", query=query, count=len(tracks))
        return tracks

    async def resolve_url(self, sc_url: str) -> dict:
        if not self._client_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SoundCloud search is not configured",
            )
        try:
            async with (
                soundcloud_slot(
                    timeout_seconds=(
                        settings.soundcloud_slot_acquire_timeout_seconds
                    ),
                ),
                httpx.AsyncClient(timeout=10) as client,
            ):
                r = await client.get(
                    f"{_SC_API_BASE}/resolve",
                    params={
                        "url": sc_url,
                        "client_id": self._client_id,
                    },
                )
                if r.status_code == 404:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=("SoundCloud track not found or private"),
                    )
                if r.status_code == 401:
                    raise HTTPException(
                        status_code=(status.HTTP_503_SERVICE_UNAVAILABLE),
                        detail=(
                            "SoundCloud client_id expired, "
                            "update SC_CLIENT_ID"
                        ),
                    )
                r.raise_for_status()
                return r.json()
        except SoundCloudSemaphoreTimeout as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SoundCloud is busy, retry later",
            ) from exc

    async def get_stream_info(
        self,
        sc_url: str,
        prefer_hls: bool = False,
    ) -> tuple[str, str]:
        sc_data = await self.resolve_url(sc_url)
        transcodings: list[dict] = sc_data.get("media", {}).get(
            "transcodings", []
        )
        track_auth: str = sc_data.get("track_authorization", "")

        protocols = (
            ["hls", "progressive"] if prefer_hls else ["progressive", "hls"]
        )
        selected: dict | None = None
        for protocol in protocols:
            selected = next(
                (
                    t
                    for t in transcodings
                    if t.get("format", {}).get("protocol") == protocol
                    and not t.get("snipped")
                ),
                None,
            )
            if selected:
                break

        if not selected:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No streamable format found for this SC track",
            )

        params: dict = {"client_id": self._client_id}
        if track_auth:
            params["track_authorization"] = track_auth

        try:
            async with (
                soundcloud_slot(
                    timeout_seconds=(
                        settings.soundcloud_slot_acquire_timeout_seconds
                    ),
                ),
                httpx.AsyncClient(timeout=10) as client,
            ):
                r = await client.get(selected["url"], params=params)
                if r.status_code in (401, 403):
                    raise HTTPException(
                        status_code=(status.HTTP_503_SERVICE_UNAVAILABLE),
                        detail=(
                            "SoundCloud client_id expired, "
                            "update SC_CLIENT_ID"
                        ),
                    )
                r.raise_for_status()
                return (
                    r.json()["url"],
                    selected.get("format", {}).get("protocol", "progressive"),
                )
        except SoundCloudSemaphoreTimeout as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SoundCloud is busy, retry later",
            ) from exc

    async def get_stream_url(self, sc_url: str) -> str:
        url, _ = await self.get_stream_info(sc_url)
        return url

    async def get_hls_url(self, sc_url: str) -> str:
        url, _ = await self.get_stream_info(sc_url, prefer_hls=True)
        return url

    async def import_or_get_track(
        self,
        sc_data: dict,
        uploader_id: int,
        is_public: bool = True,
    ) -> Track:
        sc_url: str = sc_data.get("permalink_url", "")
        if sc_url:
            existing = await self._fetch_by_sc_url(sc_url)
            if existing:
                return existing

        cover_key: str | None = None
        artwork_url: str | None = sc_data.get("artwork_url")
        if artwork_url:
            try:
                cover_key = await self._download_thumbnail(
                    artwork_url, uploader_id
                )
            except Exception:
                logger.warning(
                    "sc_thumbnail_download_failed",
                    artwork_url=artwork_url,
                )

        user_data = sc_data.get("user", {})
        artist = user_data.get("username") or sc_data.get("user", {}).get(
            "full_name"
        )
        duration_ms: int | None = sc_data.get("duration")
        duration_sec = duration_ms // 1000 if duration_ms else None

        new_values = {
            "title": sc_data.get("title", "Unknown"),
            "artist": artist,
            "duration_seconds": duration_sec,
            "source": "soundcloud",
            "catalog_type": "external_reference",
            "access_mode": "third_party_stream",
            "source_platform": "soundcloud",
            "sc_url": sc_url or None,
            "sc_uri": sc_data.get("uri"),
            "source_url": sc_url or None,
            "canonical_source_url": sc_url or None,
            "source_name": "SoundCloud",
            "file_key": None,
            "cover_key": cover_key,
            "uploaded_by_id": uploader_id,
            "is_public": is_public,
        }

        if sc_url:
            stmt = (
                pg_insert(Track)
                .values(**new_values)
                .on_conflict_do_nothing(
                    index_elements=["sc_url"],
                    index_where=sql_text("sc_url IS NOT NULL"),
                )
                .returning(Track)
            )
            result = await self._session.execute(stmt)
            track = result.scalar_one_or_none()
            await self._session.commit()
            if track is None:
                existing = await self._fetch_by_sc_url(sc_url)
                if existing is None:
                    raise RuntimeError(
                        "sc_url ON CONFLICT triggered but row "
                        "not found on re-select; possible "
                        "concurrent delete?"
                    )
                logger.info(
                    "sc_track_dedup_race_resolved",
                    sc_url=sc_url,
                    track_id=existing.id,
                )
                return existing
            await self._session.refresh(track)
            logger.info(
                "sc_track_imported",
                sc_url=sc_url,
                track_id=track.id,
            )
            return track

        track = Track(**new_values)
        self._session.add(track)
        await self._session.commit()
        await self._session.refresh(track)
        logger.info(
            "sc_track_imported",
            sc_url=sc_url,
            track_id=track.id,
        )
        return track

    async def _fetch_by_sc_url(self, sc_url: str) -> Track | None:
        result = await self._session.execute(
            select(Track).where(Track.sc_url == sc_url)
        )
        return result.scalar_one_or_none()

    async def _download_thumbnail(self, url: str, user_id: int | None) -> str:
        large_url = url.replace("-large.jpg", "-t500x500.jpg")
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(large_url)
            if r.status_code != 200:
                r2 = await client.get(url)
                r2.raise_for_status()
                data = r2.content
                content_type = r2.headers.get("content-type", "image/jpeg")
            else:
                data = r.content
                content_type = r.headers.get("content-type", "image/jpeg")
        return await s3.upload_cover(
            data=data,
            content_type=content_type.split(";")[0].strip(),
            user_id=user_id,
        )
