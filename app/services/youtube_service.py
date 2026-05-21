import asyncio
import re

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


def _yt_mix_flat_sync(seed_video_id: str, limit: int) -> list[dict]:
    import yt_dlp

    vid = (seed_video_id or "").strip()
    if len(vid) != 11:
        return []
    cap = max(1, min(int(limit), 20))
    mix_list = f"RD{vid}"
    url = f"https://www.youtube.com/playlist?list={mix_list}"
    opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "extract_flat": "in_playlist",
        "playlistend": cap,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(
            url,
            download=False,
        )
    if not info:
        return []
    entries: list[dict] = [e for e in (info.get("entries") or []) if e]
    out: list[dict] = []
    for e in entries:
        eid: str = (e.get("id") or "").strip()
        if not eid or len(eid) != 11:
            continue
        if eid == vid:
            continue
        out.append(
            {
                "id": eid,
                "title": (e.get("title") or "Unknown").strip(),
                "uploader": e.get("uploader"),
                "duration": e.get("duration"),
            }
        )
        if len(out) >= cap:
            break
    return out


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
        artist = str(artist) if artist else None
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

_YT_DLP_CLIENT_FALLBACKS: tuple[dict, ...] = (
    {},
    {
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios"],
            },
        },
    },
    {
        "extractor_args": {
            "youtube": {
                "player_client": [
                    "android",
                    "tv_embedded",
                ],
                "skip": ["webpage"],
            },
        },
    },
)
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
    last_exc: Exception | None = None
    for idx, extra in enumerate(_YT_DLP_CLIENT_FALLBACKS):
        opts: dict = {
            **_YT_DLP_BASE_OPTS,
            **extra,
            "format": fmt,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            if info is None:
                raise ValueError("yt-dlp returned no info")
            return info  # type: ignore[return-value]
        except Exception as exc:
            last_exc = exc
            msg = str(exc)
            is_format = "Requested format is not available" in msg
            is_bot_gate = "Sign in to confirm you" in msg
            if not is_format and not is_bot_gate:
                raise
            logger.warning(
                "yt_extract_fallback_attempt",
                url=url,
                requested_format=fmt,
                fallback_index=idx,
                reason=(
                    "format_unavailable"
                    if is_format
                    else "youtube_bot_gate"
                ),
            )
            if idx == len(_YT_DLP_CLIENT_FALLBACKS) - 1:
                break

    # Last chance: remove explicit format to let yt-dlp pick any stream.
    auto_last: dict = {**_YT_DLP_BASE_OPTS}
    try:
        with yt_dlp.YoutubeDL(auto_last) as ydl:
            info_auto = ydl.extract_info(url, download=False)
        if info_auto is None:
            raise ValueError("yt-dlp returned no info")
        logger.info(
            "yt_format_fallback_to_auto",
            url=url,
            requested_format=fmt,
        )
        return info_auto  # type: ignore[return-value]
    except Exception as auto_exc:
        if last_exc is not None:
            raise last_exc from auto_exc
        raise


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


def _yt_is_bot_gate_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return (
        "sign in to confirm you" in msg
        or "not a bot" in msg
        or "cookies-from-browser" in msg
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


# TODO: Re-enable YouTube after proxy support is added.
# Google bot-gate and 429 responses make direct server-IP requests unreliable
# at scale (1000+ users). Required: residential proxy pool or YouTube Data
# API v3 + key rotation. Set YOUTUBE_ENABLED=true in .env to re-enable.
class YouTubeService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _require_enabled() -> None:
        if not settings.youtube_enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "YouTube integration is temporarily disabled. "
                    "Proxy support is required for reliable operation "
                    "at scale. "
                    "Set YOUTUBE_ENABLED=true once a proxy pool is configured."
                ),
            )

    async def search(self, q: str, limit: int = 10) -> list[dict]:
        self._require_enabled()
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

    async def list_mix_video_rows(
        self, seed_video_id: str, limit: int
    ) -> list[dict]:
        self._require_enabled()
        try:
            async with youtube_slot():
                return await asyncio.to_thread(
                    _yt_mix_flat_sync, seed_video_id, limit
                )
        except OutboundSemaphoreTimeout:
            return []
        except Exception as exc:
            logger.warning(
                "yt_mix_extract_failed",
                error=str(exc),
            )
            return []

    async def resolve_url(self, yt_url: str) -> dict:
        self._require_enabled()
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
            if _yt_is_bot_gate_error(exc):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="YouTube временно ограничил доступ к видео. "
                    "Попробуйте снова позже.",
                ) from exc
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Не удалось получить информацию о видео. "
                "Проверьте ссылку или попробуйте позже.",
            ) from exc
        return info

    async def get_stream_info(
        self, yt_url: str
    ) -> tuple[str, str]:
        self._require_enabled()
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
            if _yt_is_bot_gate_error(exc):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="YouTube временно ограничил выдачу потока. "
                    "Попробуйте позже.",
                ) from exc
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
            "uploaded_by_id": None,
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
