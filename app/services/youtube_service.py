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
from app.services.outbound_semaphore import (
    OutboundSemaphoreTimeout,
    youtube_slot,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_YT_ID_RE = re.compile(
    r"(?:v=|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})"
)


def _canonical_yt_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def _extract_video_id(url: str) -> str | None:
    m = _YT_ID_RE.search(url)
    return m.group(1) if m else None


def _yt_search_sync(query: str, limit: int) -> list[dict]:
    import yt_dlp

    cap = max(1, min(int(limit), 20))
    opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "extract_flat": "in_playlist",
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(
            f"ytsearch{cap}:{query}",
            download=False,
        )
    if not info:
        return []
    entries: list[dict] = [e for e in (info.get("entries") or []) if e]
    out: list[dict] = []
    for e in entries:
        if len(out) >= cap:
            break
        vid = (e.get("id") or "").strip()
        if not vid or len(vid) != 11:
            u = (e.get("url") or "").split("v=")[-1].split("&")[0]
            if len(u) == 11:
                vid = u
        if not vid or len(vid) != 11:
            continue
        title = (e.get("title") or "Unknown").strip()
        artist = e.get("uploader") or e.get("channel") or e.get("uploader_id")
        if artist:
            artist = str(artist)
        else:
            artist = None
        dur: int | None = e.get("duration")
        if dur is not None:
            dur = int(dur)
        thumb: str | None = e.get("thumbnail")
        if not thumb:
            th = e.get("thumbnails") or []
            if th:
                thumb = th[0].get("url")
        out.append(
            {
                "video_id": vid,
                "title": title,
                "artist": artist,
                "duration_seconds": dur,
                "thumbnail_url": thumb,
                "watch_url": _canonical_yt_url(vid),
            }
        )
    return out


# Prefer itags / non-manifest URLs. HLS (.m3u8) to googlevideo fails in
# the browser: hls.js fetches without CORS. A single-URL https stream
# is proxied same-origin in ``playback.audio_stream`` like Bandcamp.
_YT_DLP_BASE_OPTS: dict = {
    "quiet": True,
    "no_warnings": True,
    "noprogress": True,
    "skip_download": True,
    "extractor_args": {
        "youtube": {
            "player_client": ["web", "android", "ios"],
        },
    },
}
# Itag-first, then m4a/webm; last ``best`` can still be HLS — we reject m3u8
# in ``_yt_pick_stream_url`` and in ``_yt_extract_stream_pair`` retry.
_YT_FORMAT_PROGRESSIVE: str = (
    "140/141/139/251/250/249/9/0/"
    "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best"
)
# Last resort: itags only.
_YT_FORMAT_ITAG_FALLBACK: str = "140/141/139/251/250/249/9/0"


def _yt_stream_protocol(url: str, meta: dict) -> str:
    """If yt-dlp gives an HLS master (.m3u8), we must return ``hls`` so the
    client uses hls.js. Feeding m3u8 to ``<audio src>`` (``direct``) does not
    work in browsers.
    """
    u = (url or "").lower()
    if ".m3u8" in u or "manifest/hls" in u:
        return "hls"
    p = (meta.get("protocol") or "").lower()
    if p.startswith("m3u8"):
        return "hls"
    if "m3u8" in p:
        return "hls"
    return "direct"


def _yt_extract_info(
    url: str, *, format_str: str | None = None
) -> dict:
    try:
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError("yt-dlp is not installed") from exc

    fmt = format_str or _YT_FORMAT_PROGRESSIVE
    opts: dict = {**_YT_DLP_BASE_OPTS, "format": fmt}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        msg = str(exc)
        if "Requested format is not available" not in msg:
            raise
        fallback_opts: dict = {**_YT_DLP_BASE_OPTS}
        logger.info(
            "yt_format_fallback_to_auto",
            url=url,
            requested_format=fmt,
        )
        with yt_dlp.YoutubeDL(fallback_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    if info is None:
        raise ValueError("yt-dlp returned no info")
    return info  # type: ignore[return-value]


def _yt_url_looks_hls(
    u: str | None,
) -> bool:
    if not u:
        return True
    s = u.lower()
    return (
        ".m3u8" in s
        or "manifest" in s
        or "manifest/hls" in s
    )


def _yt_pick_stream_url(
    info: dict,
) -> tuple[str, dict] | None:
    """Single merged ``info['url']`` is often a master m3u8; skip it then."""
    url: str | None = info.get("url")
    protocol_meta: dict = info
    if url and not _yt_url_looks_hls(url):
        return url, protocol_meta
    if url and _yt_url_looks_hls(url):
        url = None
    formats: list[dict] = info.get("formats") or []
    audio = [
        f
        for f in formats
        if f.get("acodec") != "none"
        and f.get("vcodec") in (None, "none", "")
        and f.get("url")
        and not _yt_url_looks_hls(f.get("url"))
    ]
    if not audio:
        return None
    best = max(
        audio,
        key=lambda f: float(
            f.get("tbr") or f.get("abr") or 0
        ),
    )
    burl: str | None = best.get("url")
    if not burl:
        return None
    return burl, best


def _yt_extract_stream_pair(
    yt_url: str,
) -> tuple[str, str]:
    """URL + ``hls``/``direct``; prefers progressive https over m3u8."""
    info = _yt_extract_info(yt_url)
    picked = _yt_pick_stream_url(info)
    if picked:
        u, meta = picked
        proto = _yt_stream_protocol(u, meta)
        if proto != "hls":
            return u, proto
    # Retry with a tighter itag list to avoid HLS master manifests.
    info2 = _yt_extract_info(
        yt_url, format_str=_YT_FORMAT_ITAG_FALLBACK
    )
    picked2 = _yt_pick_stream_url(info2)
    if not picked2:
        raise ValueError("no stream url from yt-dlp")
    u2, meta2 = picked2
    p2 = _yt_stream_protocol(u2, meta2)
    if p2 == "hls":
        raise ValueError("only m3u8 HLS; cannot play in browser without proxy")
    return u2, p2


class YouTubeService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search(self, q: str, limit: int = 10) -> list[dict]:
        q = (q or "").strip()
        if not q:
            return []
        try:
            async with youtube_slot():
                rows = await asyncio.to_thread(
                    _yt_search_sync, q, limit
                )
        except OutboundSemaphoreTimeout as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="YouTube сейчас перегружен, попробуйте позже.",
            ) from exc
        return rows

    async def resolve_url(self, yt_url: str) -> dict:
        try:
            async with youtube_slot():
                info = await asyncio.to_thread(_yt_extract_info, yt_url)
        except OutboundSemaphoreTimeout as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="YouTube сейчас перегружен, попробуйте позже.",
            ) from exc
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
            async with youtube_slot():
                pair: tuple[str, str] = await asyncio.to_thread(
                    _yt_extract_stream_pair, yt_url
                )
        except OutboundSemaphoreTimeout as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="YouTube сейчас перегружен, попробуйте позже.",
            ) from exc
        except ValueError as exc:
            logger.warning(
                "yt_stream_hls_or_missing",
                error=str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Для этого видео нет прямого аудио (только HLS) "
                "— воспроизведение в браузере сейчас не поддерживается.",
            ) from exc
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
        return pair

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
