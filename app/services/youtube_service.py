import asyncio
import re

import httpx
import structlog
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import s3
from app.models.track import Track

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_YT_ID_RE = re.compile(
    r"(?:v=|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})"
)


def _canonical_yt_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def _extract_video_id(url: str) -> str | None:
    m = _YT_ID_RE.search(url)
    return m.group(1) if m else None


def _yt_extract_info(url: str) -> dict:
    try:
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError("yt-dlp is not installed") from exc

    opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "skip_download": True,
        "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if info is None:
        raise ValueError("yt-dlp returned no info")
    return info  # type: ignore[return-value]


class YouTubeService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve_url(self, yt_url: str) -> dict:
        try:
            info = await asyncio.to_thread(_yt_extract_info, yt_url)
        except Exception as exc:
            logger.warning(
                "yt_resolve_failed",
                error=str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Не удалось получить информацию о видео. "
                "Проверьте ссылку или попробуйте позже.",
            ) from exc
        return info

    async def get_stream_info(
        self, yt_url: str
    ) -> tuple[str, str]:
        try:
            info = await asyncio.to_thread(_yt_extract_info, yt_url)
        except Exception as exc:
            logger.warning(
                "yt_stream_failed",
                error=str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Не удалось получить поток YouTube. "
                "Попробуйте позже.",
            ) from exc

        url: str | None = info.get("url")
        if not url:
            formats: list[dict] = info.get("formats") or []
            audio = [
                f
                for f in formats
                if f.get("acodec") != "none"
                and f.get("vcodec") in (None, "none", "")
                and f.get("url")
            ]
            if audio:
                best = max(
                    audio,
                    key=lambda f: (
                        f.get("tbr") or f.get("abr") or 0
                    ),
                )
                url = best.get("url")

        if not url:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Для этого видео не найден аудио-поток.",
            )

        return url, "direct"

    async def import_or_get_track(
        self,
        yt_data: dict,
        uploader_id: int,
        is_public: bool = True,
    ) -> Track:
        video_id: str = yt_data.get("id") or ""
        if not video_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Не удалось определить ID видео.",
            )

        existing = await self._fetch_by_id(video_id)
        if existing:
            return existing

        cover_key: str | None = None
        thumbnail: str | None = yt_data.get("thumbnail")
        if not thumbnail:
            thumbs: list[dict] = yt_data.get("thumbnails") or []
            if thumbs:
                thumbnail = thumbs[-1].get("url")
        if thumbnail:
            try:
                cover_key = await self._download_thumbnail(
                    thumbnail, uploader_id
                )
            except Exception:
                logger.warning(
                    "yt_thumbnail_failed",
                    video_id=video_id,
                )

        raw_url: str = (
            yt_data.get("webpage_url")
            or yt_data.get("original_url")
            or _canonical_yt_url(video_id)
        )
        canonical = _canonical_yt_url(video_id)
        duration: int | None = yt_data.get("duration")
        artist = (
            yt_data.get("uploader")
            or yt_data.get("channel")
            or yt_data.get("creator")
        )

        new_values: dict = {
            "title": yt_data.get("title") or "Unknown",
            "artist": artist,
            "duration_seconds": (
                int(duration) if duration else None
            ),
            "source": "youtube",
            "catalog_type": "external_reference",
            "access_mode": "third_party_stream",
            "source_platform": "youtube",
            "imported_from": "youtube",
            "external_id": video_id,
            "source_url": raw_url,
            "canonical_source_url": canonical,
            "source_name": "YouTube",
            "file_key": None,
            "cover_key": cover_key,
            "uploaded_by_id": uploader_id,
            "is_public": is_public,
        }

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
            existing = await self._fetch_by_id(video_id)
            if existing is None:
                raise RuntimeError(
                    "youtube ON CONFLICT triggered but row not found"
                )
            logger.info(
                "yt_track_dedup",
                video_id=video_id,
                track_id=existing.id,
            )
            from app.services.search_index_notify import (
                schedule_reindex_track,
            )

            await schedule_reindex_track(existing.id)
            return existing

        await self._session.refresh(track)
        logger.info(
            "yt_track_imported",
            video_id=video_id,
            track_id=track.id,
        )
        from app.services.search_index_notify import (
            schedule_reindex_track,
        )

        await schedule_reindex_track(track.id)
        return track

    async def _fetch_by_id(self, video_id: str) -> Track | None:
        result = await self._session.execute(
            select(Track).where(
                Track.external_id == video_id,
                Track.imported_from == "youtube",
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
