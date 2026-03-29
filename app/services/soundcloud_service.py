from urllib.parse import quote

import httpx
import structlog
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import s3
from app.models.track import Track

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_SC_API_BASE = "https://api-v2.soundcloud.com"
_SC_OEMBED_URL = "https://soundcloud.com/oembed"


class SoundCloudService:
    def __init__(self, client_id: str, session: AsyncSession) -> None:
        self._client_id = client_id
        self._session = session

    async def search(
        self, query: str, limit: int = 20
    ) -> list[dict]:
        if not self._client_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SoundCloud search is not configured",
            )
        async with httpx.AsyncClient(timeout=10) as client:
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
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="SoundCloud client_id expired, update SC_CLIENT_ID",
                )
            r.raise_for_status()
            data = r.json()
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
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{_SC_API_BASE}/resolve",
                params={"url": sc_url, "client_id": self._client_id},
            )
            if r.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="SoundCloud track not found or private",
                )
            if r.status_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="SoundCloud client_id expired, update SC_CLIENT_ID",
                )
            r.raise_for_status()
            return r.json()

    async def get_stream_url(self, sc_url: str) -> str:
        sc_data = await self.resolve_url(sc_url)
        transcodings: list[dict] = (
            sc_data.get("media", {}).get("transcodings", [])
        )
        track_auth: str = sc_data.get("track_authorization", "")

        progressive = next(
            (
                t for t in transcodings
                if t.get("format", {}).get("protocol") == "progressive"
                and not t.get("snipped")
            ),
            None,
        )
        if not progressive:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No streamable format found for this SC track",
            )

        params: dict = {"client_id": self._client_id}
        if track_auth:
            params["track_authorization"] = track_auth

        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(progressive["url"], params=params)
            if r.status_code in (401, 403):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="SoundCloud client_id expired, update SC_CLIENT_ID",
                )
            r.raise_for_status()
            return r.json()["url"]

    async def import_or_get_track(
        self,
        sc_data: dict,
        uploader_id: int | None = None,
        is_public: bool = True,
    ) -> Track:
        sc_url: str = sc_data.get("permalink_url", "")
        existing_result = await self._session.execute(
            select(Track).where(Track.sc_url == sc_url)
        )
        existing = existing_result.scalar_one_or_none()
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
                    "sc_thumbnail_download_failed", artwork_url=artwork_url
                )

        user_data = sc_data.get("user", {})
        artist = user_data.get("username") or sc_data.get("user", {}).get(
            "full_name"
        )
        duration_ms: int | None = sc_data.get("duration")
        duration_sec = duration_ms // 1000 if duration_ms else None

        track = Track(
            title=sc_data.get("title", "Unknown"),
            artist=artist,
            duration_seconds=duration_sec,
            source="soundcloud",
            sc_url=sc_url,
            sc_uri=sc_data.get("uri"),
            file_key=None,
            cover_key=cover_key,
            uploaded_by_id=uploader_id,
            is_public=is_public,
        )
        self._session.add(track)
        await self._session.commit()
        await self._session.refresh(track)
        logger.info("sc_track_imported", sc_url=sc_url, track_id=track.id)
        return track

    async def _download_thumbnail(
        self, url: str, user_id: int | None
    ) -> str:
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
