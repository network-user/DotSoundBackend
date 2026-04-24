import html
import json
import re

import httpx
import structlog
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import s3
from app.config import settings
from app.models.track import Track
from app.services.outbound_semaphore import (
    OutboundSemaphoreTimeout,
    bandcamp_slot,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_TRALBUM_ATTR_RE = re.compile(
    r'data-tralbum="([^"]+)"', re.DOTALL
)
_TRALBUM_VAR_RE = re.compile(
    r"var TralbumData\s*=\s*(\{.*?\})\s*;", re.DOTALL
)
_PAGEDATA_RE = re.compile(
    r'<script[^>]+id="pagedata"[^>]*>(\{.*?\})</script>',
    re.DOTALL,
)


def _parse_tralbum(page_html: str) -> dict:
    m = _TRALBUM_ATTR_RE.search(page_html)
    if m:
        return json.loads(html.unescape(m.group(1)))

    m = _TRALBUM_VAR_RE.search(page_html)
    if m:
        return json.loads(m.group(1))

    m = _PAGEDATA_RE.search(page_html)
    if m:
        outer = json.loads(m.group(1))
        if "TralbumData" in outer:
            return outer["TralbumData"]

    raise ValueError("No TralbumData found in Bandcamp page")


class BandcampService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _fetch_page(self, bc_url: str) -> str:
        try:
            async with bandcamp_slot():
                async with httpx.AsyncClient(
                    timeout=15,
                    headers={
                        "User-Agent": (
                            settings.outbound_user_agent
                        ),
                        "Accept-Language": "en-US,en;q=0.9",
                    },
                    follow_redirects=True,
                ) as client:
                    r = await client.get(bc_url)
                    if r.status_code == 404:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail="Трек не найден на Bandcamp.",
                        )
                    r.raise_for_status()
                    return r.text
        except OutboundSemaphoreTimeout as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Bandcamp сейчас перегружен, попробуйте позже.",
            ) from exc

    async def resolve_url(self, bc_url: str) -> dict:
        try:
            page = await self._fetch_page(bc_url)
            data = _parse_tralbum(page)
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning(
                "bc_resolve_failed",
                error=str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Не удалось получить данные трека с Bandcamp. "
                "Убедитесь, что это ссылка на конкретный трек.",
            ) from exc

        tracks: list[dict] = data.get("trackinfo") or []
        if not tracks:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="На этой странице нет трека для импорта.",
            )

        data["_bc_page_url"] = bc_url
        return data

    async def get_stream_info(
        self, bc_url: str
    ) -> tuple[str, str]:
        try:
            page = await self._fetch_page(bc_url)
            data = _parse_tralbum(page)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Не удалось получить поток с Bandcamp.",
            ) from exc

        tracks: list[dict] = data.get("trackinfo") or []
        if not tracks:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Трек не найден в данных Bandcamp.",
            )

        file_info: dict = tracks[0].get("file") or {}
        stream_url: str | None = (
            file_info.get("mp3-128")
            or file_info.get("mp3-v0")
            or file_info.get("mp3-320")
        )
        if not stream_url:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Этот трек недоступен для свободного "
                "прослушивания на Bandcamp.",
            )

        return stream_url, "direct"

    async def import_or_get_track(
        self,
        bc_data: dict,
        uploader_id: int,
        is_public: bool = True,
    ) -> Track:
        tracks: list[dict] = bc_data.get("trackinfo") or []
        if not tracks:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Нет данных трека в Bandcamp-ответе.",
            )
        track_info = tracks[0]

        track_id_raw = track_info.get("track_id") or track_info.get("id")
        bc_track_id: str | None = (
            str(track_id_raw) if track_id_raw else None
        )

        if bc_track_id:
            existing = await self._fetch_by_id(bc_track_id)
            if existing:
                return existing

        cover_key: str | None = None
        artwork_url: str | None = bc_data.get("art_url")
        if artwork_url:
            try:
                cover_key = await self._download_thumbnail(
                    artwork_url, uploader_id
                )
            except Exception:
                logger.warning(
                    "bc_thumbnail_failed",
                    bc_track_id=bc_track_id,
                )

        duration_sec: int | None = None
        raw_dur = track_info.get("duration")
        if raw_dur:
            duration_sec = int(raw_dur)

        bc_page_url: str = bc_data.get("_bc_page_url") or ""
        canonical = bc_page_url

        artist = bc_data.get("artist") or bc_data.get("band_name")
        title: str = (
            track_info.get("title")
            or bc_data.get("current", {}).get("title")
            or "Unknown"
        )

        new_values: dict = {
            "title": title,
            "artist": artist,
            "duration_seconds": duration_sec,
            "source": "bandcamp",
            "catalog_type": "external_reference",
            "access_mode": "third_party_stream",
            "source_platform": "bandcamp",
            "imported_from": "bandcamp",
            "external_id": bc_track_id,
            "source_url": bc_page_url or None,
            "canonical_source_url": canonical or None,
            "source_name": "Bandcamp",
            "file_key": None,
            "cover_key": cover_key,
            "uploaded_by_id": uploader_id,
            "is_public": is_public,
        }

        if bc_track_id:
            stmt = (
                pg_insert(Track)
                .values(**new_values)
                .on_conflict_do_nothing(
                    index_elements=["imported_from", "external_id"],
                    index_where=sql_text("external_id IS NOT NULL"),
                )
                .returning(Track)
            )
            result = await self._session.execute(stmt)
            track = result.scalar_one_or_none()
            await self._session.commit()

            if track is None:
                existing = await self._fetch_by_id(bc_track_id)
                if existing is None:
                    raise RuntimeError(
                        "bandcamp ON CONFLICT triggered but row not found"
                    )
                logger.info(
                    "bc_track_dedup",
                    bc_track_id=bc_track_id,
                    track_id=existing.id,
                )
                from app.services.search_index_notify import (
                    schedule_reindex_track,
                )

                await schedule_reindex_track(existing.id)
                return existing
        else:
            track_obj = Track(**new_values)
            self._session.add(track_obj)
            await self._session.commit()
            track = track_obj

        await self._session.refresh(track)
        logger.info(
            "bc_track_imported",
            bc_track_id=bc_track_id,
            track_id=track.id,
        )
        from app.services.search_index_notify import (
            schedule_reindex_track,
        )

        await schedule_reindex_track(track.id)
        return track

    async def _fetch_by_id(self, bc_track_id: str) -> Track | None:
        result = await self._session.execute(
            select(Track).where(
                Track.external_id == bc_track_id,
                Track.imported_from == "bandcamp",
            )
        )
        return result.scalar_one_or_none()

    async def _download_thumbnail(
        self, url: str, user_id: int | None
    ) -> str:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
            r.raise_for_status()
        return await s3.upload_cover(
            data=r.content,
            content_type=(
                r.headers.get("content-type", "image/jpeg")
                .split(";")[0]
                .strip()
            ),
            user_id=user_id,
        )
