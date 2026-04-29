import re
from typing import Any

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
from app.repositories.artist import ArtistRepository
from app.services.sc_semaphore import (
    SoundCloudSemaphoreTimeout,
    soundcloud_slot,
)
from app.services.url_cache import (
    CACHE_KEY_SC,
    get_cached_stream,
    set_cached_stream,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_SC_API_BASE = "https://api-v2.soundcloud.com"

_SC_STATION_SYNTHETIC_ID_OFFSET = 10**15

_SC_TRACKS_IDS_BATCH_SIZE = 50


def synthetic_soundcloud_id_for_artist_station(
    soundcloud_user_id: int,
) -> int:
    return -(_SC_STATION_SYNTHETIC_ID_OFFSET + int(soundcloud_user_id))


def normalize_soundcloud_permalink(
    raw: str | None,
) -> str | None:
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None
    if "soundcloud.com/" in s:
        tail = s.split("soundcloud.com/", 1)[-1]
        slug = tail.strip("/").split("/")[0]
        return slug.lower() if slug else None
    return s.strip("/").lower() or None


def extract_soundcloud_profile_permalink_from_url(
    url: str | None,
) -> str | None:
    if not url or not isinstance(url, str):
        return None
    s = url.strip()
    low = s.lower()
    if "soundcloud.com/" not in low:
        return None
    tail = s.split("soundcloud.com/", 1)[-1]
    path = tail.split("?", 1)[0].strip("/")
    if not path:
        return None
    slug = path.split("/")[0]
    noise = frozenset(
        {
            "tracks",
            "likes",
            "sets",
            "followers",
            "following",
            "popular-tracks",
        }
    )
    if slug.lower() in noise:
        return None
    return normalize_soundcloud_permalink(slug)


_SC_OEMBED_URL = "https://soundcloud.com/oembed"

_MAX_SC_USER_SEARCH_QUERY_LEN = 120


class SoundCloudService:
    def __init__(self, client_id: str, session: AsyncSession) -> None:
        self._client_id = client_id
        self._session = session

    def _sc_client(
        self, timeout: float = 10, **kwargs: object
    ) -> httpx.AsyncClient:
        """Return an AsyncClient routed through Tor if the pool is active."""
        from app.services.tor_pool import get_outbound_proxy

        proxy = get_outbound_proxy("soundcloud")
        return httpx.AsyncClient(timeout=timeout, proxy=proxy, **kwargs)  # type: ignore[arg-type]

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
                self._sc_client() as client,
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
                            "SoundCloud: неверный или устаревший "
                            "SC_CLIENT_ID. Обновите в .env и перезапустите."
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

    async def get_charts(
        self,
        genre: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Fetch top-chart tracks from the external provider."""
        if not self._client_id:
            return []
        params: dict = {
            "kind": "top",
            "client_id": self._client_id,
            "limit": limit,
            "linked_partitioning": 1,
        }
        if genre:
            params["genre"] = f"soundcloud:genres:{genre.lower()}"
        try:
            async with (
                soundcloud_slot(
                    timeout_seconds=(
                        settings.soundcloud_slot_acquire_timeout_seconds
                    ),
                ),
                self._sc_client() as client,
            ):
                r = await client.get(
                    f"{_SC_API_BASE}/charts",
                    params=params,
                )
                if r.status_code in (401, 429):
                    logger.warning(
                        "sc_charts_error",
                        status=r.status_code,
                    )
                    return []
                r.raise_for_status()
                data = r.json()
        except (SoundCloudSemaphoreTimeout, Exception) as exc:
            logger.warning("sc_charts_failed", error=str(exc))
            return []
        return [
            item["track"]
            for item in data.get("collection", [])
            if isinstance(item.get("track"), dict)
            and item["track"].get("streamable")
        ]

    async def get_trending(self, limit: int = 20) -> list[dict]:
        """Global trending tracks via charts or popular search fallback."""
        result = await self.get_charts(genre="all-music", limit=limit)
        if result:
            return result
        return await self._get_popular_fallback(limit)

    async def _get_popular_fallback(self, limit: int = 20) -> list[dict]:
        """Fallback: search for popular tracks when charts are unavailable."""
        if not self._client_id:
            return []
        params = {
            "q": "popular",
            "client_id": self._client_id,
            "limit": limit,
            "linked_partitioning": 1,
        }
        try:
            async with (
                soundcloud_slot(
                    timeout_seconds=(
                        settings.soundcloud_slot_acquire_timeout_seconds
                    ),
                ),
                self._sc_client() as client,
            ):
                r = await client.get(
                    f"{_SC_API_BASE}/tracks",
                    params=params,
                )
                if r.status_code != 200:
                    return []
                r.raise_for_status()
                data = r.json()
        except Exception as exc:
            logger.warning(
                "sc_popular_fallback_failed",
                error=str(exc),
            )
            return []
        collection = (
            data if isinstance(data, list) else data.get("collection", [])
        )
        return [
            t
            for t in collection
            if isinstance(t, dict) and t.get("streamable")
        ][:limit]

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
                self._sc_client() as client,
            ):
                r = await client.get(
                    f"{_SC_API_BASE}/resolve",
                    params={
                        "url": sc_url,
                        "client_id": self._client_id,
                    },
                )
                if r.status_code == 404:
                    logger.warning(
                        "sc_resolve_404",
                        sc_url_len=len(sc_url),
                        sc_url_host=(
                            (sc_url.split("://", 1)[-1].split("/", 1)[0])
                            if "://" in sc_url
                            else "?"
                        ),
                    )
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=(
                            "SoundCloud: трек не найден по ссылке "
                            "(удалён, приватный или в базе устарел URL). "
                            "Проверьте трек на soundcloud.com или "
                            "импортируйте снова."
                        ),
                    )
                if r.status_code == 401:
                    raise HTTPException(
                        status_code=(status.HTTP_503_SERVICE_UNAVAILABLE),
                        detail=(
                            "SoundCloud: неверный или устаревший "
                            "SC_CLIENT_ID. Обновите в .env и перезапустите."
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
        *,
        use_cache: bool = True,
    ) -> tuple[str, str]:
        """Resolve stream URL. ``use_cache=False`` skips Redis — needed for
        short-lived ``cf-media.sndcdn.com`` signed URLs (TTL can exceed the
        signature window).
        """
        cache_id = f"{sc_url}:{'hls' if prefer_hls else 'progressive'}"
        if use_cache:
            cached = await get_cached_stream(CACHE_KEY_SC, cache_id)
            if cached:
                logger.debug(
                    "stream_url_cache_hit",
                    service="soundcloud",
                    sc_url=sc_url,
                )
                return cached

        sc_data = await self.resolve_url(sc_url)
        transcodings: list[dict] = sc_data.get("media", {}).get(
            "transcodings", []
        )
        track_auth: str = sc_data.get("track_authorization", "")

        protocols_order = (
            ["hls", "progressive"] if prefer_hls else ["progressive", "hls"]
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
                self._sc_client() as client,
            ):
                attempted = False
                saw_manifest_404 = False
                for protocol in protocols_order:
                    selected = next(
                        (
                            t
                            for t in transcodings
                            if t.get("format", {}).get("protocol")
                            == protocol
                            and not t.get("snipped")
                        ),
                        None,
                    )
                    if not selected:
                        continue
                    attempted = True
                    r = await client.get(selected["url"], params=params)
                    if r.status_code in (401, 403):
                        raise HTTPException(
                            status_code=(status.HTTP_503_SERVICE_UNAVAILABLE),
                            detail=(
                                "SoundCloud: неверный или устаревший "
                                "SC_CLIENT_ID. Обновите в .env "
                                "и перезапустите."
                            ),
                        )
                    if r.status_code == 404:
                        saw_manifest_404 = True
                        logger.warning(
                            "soundcloud_transcoding_manifest_404",
                            protocol=protocol,
                        )
                        continue
                    if not r.is_success:
                        logger.warning(
                            "soundcloud_transcoding_http_error",
                            status_code=r.status_code,
                            protocol=protocol,
                        )
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail="SoundCloud upstream error",
                        )
                    stream_url: str = r.json()["url"]
                    protocol_out: str = selected.get("format", {}).get(
                        "protocol", protocol
                    )
                    await set_cached_stream(
                        CACHE_KEY_SC,
                        cache_id,
                        stream_url,
                        protocol_out,
                        settings.stream_url_cache_ttl_soundcloud,
                    )
                    return stream_url, protocol_out

                if not attempted:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="No streamable format found for this SC track",
                    )
                if saw_manifest_404:
                    logger.warning(
                        "soundcloud_stream_unavailable_all_formats",
                        sc_host="api-v2.soundcloud.com",
                    )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="SoundCloud stream unavailable",
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

    async def list_user_albums(
        self,
        soundcloud_user_id: int,
        *,
        limit_per_page: int = 50,
        max_total: int | None = None,
    ) -> tuple[list[dict[str, Any]], bool]:
        if not self._client_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SoundCloud search is not configured",
            )
        collected: list[dict[str, Any]] = []
        truncated = False
        next_url: str | None = (
            f"{_SC_API_BASE}/users/{soundcloud_user_id}/albums"
        )
        params: dict[str, str | int] | None = {
            "client_id": self._client_id,
            "linked_partitioning": 1,
            "limit": limit_per_page,
        }
        try:
            while next_url is not None:
                async with (
                    soundcloud_slot(
                        timeout_seconds=(
                            settings.soundcloud_slot_acquire_timeout_seconds
                        ),
                    ),
                    self._sc_client() as client,
                ):
                    if params is not None:
                        r = await client.get(next_url, params=params)
                        params = None
                    else:
                        r = await client.get(next_url)
                    if r.status_code == 401:
                        raise HTTPException(
                            status_code=(status.HTTP_503_SERVICE_UNAVAILABLE),
                            detail=(
                                "SoundCloud: неверный или устаревший "
                                "SC_CLIENT_ID. Обновите в .env "
                                "и перезапустите."
                            ),
                        )
                    r.raise_for_status()
                    data = r.json()
                chunk = data.get("collection", [])
                if isinstance(chunk, list):
                    collected.extend([x for x in chunk if isinstance(x, dict)])
                if max_total is not None and len(collected) >= max_total:
                    collected = collected[:max_total]
                    href = data.get("next_href")
                    truncated = isinstance(href, str) and bool(href)
                    next_url = None
                    break
                href = data.get("next_href")
                next_url = href if isinstance(href, str) else None
        except SoundCloudSemaphoreTimeout as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SoundCloud is busy, retry later",
            ) from exc
        logger.info(
            "sc_user_albums_done",
            soundcloud_user_id=soundcloud_user_id,
            count=len(collected),
            truncated=truncated,
        )
        return collected, truncated

    async def fetch_playlist_by_id(
        self,
        playlist_id: int,
    ) -> dict[str, Any]:
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
                self._sc_client() as client,
            ):
                r = await client.get(
                    f"{_SC_API_BASE}/playlists/{playlist_id}",
                    params={"client_id": self._client_id},
                )
                if r.status_code == 401:
                    raise HTTPException(
                        status_code=(status.HTTP_503_SERVICE_UNAVAILABLE),
                        detail=(
                            "SoundCloud: неверный или устаревший "
                            "SC_CLIENT_ID. Обновите в .env "
                            "и перезапустите."
                        ),
                    )
                r.raise_for_status()
                data = r.json()
        except SoundCloudSemaphoreTimeout as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SoundCloud is busy, retry later",
            ) from exc
        if not isinstance(data, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Unexpected SoundCloud playlist payload",
            )
        return data

    async def download_artwork_as_cover_key(
        self,
        artwork_url: str | None,
        *,
        uploader_id: int,
    ) -> str | None:
        if not artwork_url:
            return None
        try:
            return await self._download_thumbnail(artwork_url, uploader_id)
        except Exception:
            logger.warning(
                "sc_artwork_download_failed",
                artwork_url=artwork_url,
            )
            return None

    @staticmethod
    def _track_is_stub(track: dict[str, Any]) -> bool:
        if track.get("permalink_url"):
            return False
        return track.get("id") is not None

    async def fetch_track_by_id(
        self,
        soundcloud_track_id: int,
    ) -> dict[str, Any]:
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
                self._sc_client() as client,
            ):
                r = await client.get(
                    f"{_SC_API_BASE}/tracks/{soundcloud_track_id}",
                    params={"client_id": self._client_id},
                )
                if r.status_code == 401:
                    raise HTTPException(
                        status_code=(status.HTTP_503_SERVICE_UNAVAILABLE),
                        detail=(
                            "SoundCloud: неверный или устаревший "
                            "SC_CLIENT_ID. Обновите в .env "
                            "и перезапустите."
                        ),
                    )
                r.raise_for_status()
                data = r.json()
        except SoundCloudSemaphoreTimeout as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SoundCloud is busy, retry later",
            ) from exc
        if not isinstance(data, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Unexpected SoundCloud track payload",
            )
        return data

    async def expand_playlist_stub_tracks(
        self,
        playlist: dict[str, Any],
    ) -> dict[str, Any]:
        raw_tracks = playlist.get("tracks")
        if not isinstance(raw_tracks, list):
            return playlist
        out: list[Any] = []
        for item in raw_tracks:
            if not isinstance(item, dict):
                out.append(item)
                continue
            if self._track_is_stub(item):
                tid = item.get("id")
                if tid is None:
                    out.append(item)
                    continue
                full = await self.fetch_track_by_id(int(tid))
                out.append(full)
            else:
                out.append(item)
        return {**playlist, "tracks": out}

    async def fetch_tracks_by_ids_bulk(
        self,
        track_ids: list[int],
    ) -> list[dict[str, Any]]:
        if not self._client_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SoundCloud search is not configured",
            )
        if not track_ids:
            return []
        out: list[dict[str, Any]] = []
        for start in range(0, len(track_ids), _SC_TRACKS_IDS_BATCH_SIZE):
            chunk = track_ids[start : start + _SC_TRACKS_IDS_BATCH_SIZE]
            ids_param = ",".join(str(i) for i in chunk)
            try:
                async with (
                    soundcloud_slot(
                        timeout_seconds=(
                            settings.soundcloud_slot_acquire_timeout_seconds
                        ),
                    ),
                    self._sc_client() as client,
                ):
                    r = await client.get(
                        f"{_SC_API_BASE}/tracks",
                        params={
                            "ids": ids_param,
                            "client_id": self._client_id,
                        },
                    )
                    if r.status_code == 401:
                        raise HTTPException(
                            status_code=(status.HTTP_503_SERVICE_UNAVAILABLE),
                            detail=(
                                "SoundCloud: неверный или устаревший "
                                "SC_CLIENT_ID. Обновите в .env "
                                "и перезапустите."
                            ),
                        )
                    r.raise_for_status()
                    payload = r.json()
            except SoundCloudSemaphoreTimeout as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="SoundCloud is busy, retry later",
                ) from exc
            if not isinstance(payload, list):
                msg = "Unexpected SoundCloud tracks batch payload"
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=msg,
                )
            out.extend(t for t in payload if isinstance(t, dict))
        return out

    async def fetch_expanded_artist_station_playlist(
        self,
        soundcloud_user_id: int,
    ) -> dict[str, Any]:
        """Discover artist station: resolve URL then /tracks batch.

        Recon (2026-04): GET resolve with discover sets URL returns
        kind=system-playlist, string urn id, up to 50 stubs
        (id/kind/monetization_model/policy only). GET /tracks?ids=
        accepts at most 50 ids per request. /playlists/{encoded urn}
        returns 500; use resolve + tracks only.
        """
        sc_url = (
            "https://soundcloud.com/discover/sets/"
            f"artist-stations:{int(soundcloud_user_id)}"
        )
        resolved = await self.resolve_url(sc_url)
        if not isinstance(resolved, dict):
            msg = "Unexpected SoundCloud resolve payload for artist station"
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=msg,
            )
        if resolved.get("kind") != "system-playlist":
            msg = "SoundCloud resolve is not an artist station playlist"
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=msg,
            )
        raw_tracks = resolved.get("tracks")
        if not isinstance(raw_tracks, list):
            msg = "Artist station resolve missing tracks"
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=msg,
            )
        tids: list[int] = []
        for item in raw_tracks:
            if not isinstance(item, dict):
                continue
            tid = item.get("id")
            if tid is not None:
                tids.append(int(tid))
        full = await self.fetch_tracks_by_ids_bulk(tids)
        synthetic = synthetic_soundcloud_id_for_artist_station(
            soundcloud_user_id,
        )
        return {
            **resolved,
            "id": synthetic,
            "tracks": full,
        }

    async def ensure_soundcloud_ids_for_artist(
        self,
        artist_id: int,
        sc_user_id: int,
        permalink: str | None = None,
    ) -> bool:
        repo = ArtistRepository(self._session)
        artist = await repo.get_by_id(artist_id)
        if artist is None:
            logger.warning(
                "sc_ensure_ids_missing_artist",
                artist_id=artist_id,
            )
            return False
        norm = normalize_soundcloud_permalink(permalink)
        other = await repo.find_by_soundcloud_user_id(
            sc_user_id,
            exclude_artist_id=artist_id,
        )
        if other is not None:
            logger.warning(
                "sc_ensure_ids_sc_user_taken",
                artist_id=artist_id,
                sc_user_id=sc_user_id,
                other_artist_id=other.id,
            )
            return False
        existing_uid = artist.soundcloud_user_id
        if existing_uid is not None:
            if int(existing_uid) != int(sc_user_id):
                logger.warning(
                    "sc_ensure_ids_user_id_mismatch",
                    artist_id=artist_id,
                    stored_soundcloud_user_id=int(existing_uid),
                    requested_soundcloud_user_id=sc_user_id,
                )
                return False
            if norm is not None and artist.soundcloud_permalink != norm:
                artist.soundcloud_permalink = norm
                await self._session.commit()
                await self._session.refresh(artist)
            return True
        artist.soundcloud_user_id = sc_user_id
        if norm is not None:
            artist.soundcloud_permalink = norm
        await self._session.commit()
        await self._session.refresh(artist)
        logger.info(
            "sc_ensure_ids_applied",
            artist_id=artist_id,
            sc_user_id=sc_user_id,
        )
        return True

    @staticmethod
    def _soundcloud_avatar_url_is_placeholder(url: str) -> bool:
        low = url.lower()
        return "default_avatar" in low or "default-user" in low

    @staticmethod
    def _soundcloud_avatar_url_candidates(url: str) -> list[str]:
        base = url.split("?", 1)[0].strip()
        if not base:
            return []
        out: list[str] = []
        seen: set[str] = set()

        def add(u: str) -> None:
            if u and u not in seen:
                seen.add(u)
                out.append(u)

        add(base)
        add(base.replace("-large.jpg", "-t500x500.jpg"))
        add(base.replace("-large.png", "-t500x500.png"))
        add(re.sub(r"-t\d+x\d+", "-t500x500", base))
        add(base.replace("-small.jpg", "-t500x500.jpg"))
        add(base.replace("-badge.jpg", "-t500x500.jpg"))
        add(base.replace("-original.jpg", "-t500x500.jpg"))
        return out

    async def _fetch_soundcloud_avatar_bytes_cascade(
        self,
        url: str,
    ) -> tuple[bytes, str] | None:
        candidates = self._soundcloud_avatar_url_candidates(url)
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                for cand in candidates:
                    try:
                        r = await client.get(cand)
                    except httpx.HTTPError:
                        continue
                    if r.status_code != 200:
                        continue
                    ct = r.headers.get("content-type", "image/jpeg")
                    return r.content, ct.split(";")[0].strip()
        except Exception:
            return None
        return None

    async def fetch_soundcloud_user_by_id(
        self,
        soundcloud_user_id: int,
    ) -> dict[str, Any] | None:
        if not self._client_id:
            return None
        try:
            async with (
                soundcloud_slot(
                    timeout_seconds=(
                        settings.soundcloud_slot_acquire_timeout_seconds
                    ),
                ),
                self._sc_client() as client,
            ):
                r = await client.get(
                    f"{_SC_API_BASE}/users/{int(soundcloud_user_id)}",
                    params={"client_id": self._client_id},
                )
                if r.status_code in (401, 404):
                    return None
                r.raise_for_status()
                data = r.json()
        except (SoundCloudSemaphoreTimeout, Exception):
            return None
        if not isinstance(data, dict):
            return None
        return data

    @staticmethod
    def _parse_soundcloud_user_id(raw: object) -> int | None:
        if isinstance(raw, int):
            return raw
        if isinstance(raw, str) and raw.isdigit():
            return int(raw)
        return None

    @staticmethod
    def _should_refetch_soundcloud_user(user: dict[str, Any]) -> bool:
        av = user.get("avatar_url")
        if not isinstance(av, str) or not av.strip():
            return True
        return SoundCloudService._soundcloud_avatar_url_is_placeholder(
            av.strip()
        )

    async def sync_artist_soundcloud_uploader_profile(
        self,
        artist_id: int,
        user: dict[str, Any] | None,
        *,
        uploader_id: int | None,
    ) -> None:
        repo = ArtistRepository(self._session)
        artist = await repo.get_by_id(artist_id)
        if artist is None:
            return
        merged: dict[str, Any] = {}
        if isinstance(user, dict):
            merged = dict(user)
        uid = self._parse_soundcloud_user_id(
            merged.get("id"),
        )
        if uid is None and artist.soundcloud_user_id is not None:
            uid = int(artist.soundcloud_user_id)
            merged.setdefault("id", uid)
        if uid is None:
            return
        if self._should_refetch_soundcloud_user(merged):
            full = await self.fetch_soundcloud_user_by_id(uid)
            if isinstance(full, dict):
                merged = {**merged, **full}
        perm_raw = merged.get("permalink")
        perm: str | None = None
        if isinstance(perm_raw, str):
            perm = normalize_soundcloud_permalink(perm_raw)
        ids_linked = False
        if uid is not None:
            existing_uid = artist.soundcloud_user_id
            if existing_uid is not None and int(existing_uid) == uid:
                ids_linked = True
            else:
                ids_linked = await self.ensure_soundcloud_ids_for_artist(
                    artist_id,
                    uid,
                    perm,
                )
        elif artist.soundcloud_user_id is not None:
            ids_linked = True
        else:
            return
        if not ids_linked:
            return
        artist = await repo.get_by_id(artist_id)
        if artist is None or artist.image_key:
            return
        av = merged.get("avatar_url")
        if not isinstance(av, str) or not av.strip():
            logger.info(
                "sc_artist_avatar_missing_url",
                artist_id=artist_id,
            )
            return
        av = av.strip()
        if self._soundcloud_avatar_url_is_placeholder(av):
            return
        fetched = await self._fetch_soundcloud_avatar_bytes_cascade(av)
        if fetched is None:
            logger.warning(
                "sc_artist_avatar_fetch_failed",
                artist_id=artist_id,
            )
            return
        data, _ct = fetched
        try:
            img_key, _, _, _ = await s3.upload_image(
                data=data,
                prefix="artists",
                max_size=settings.image_avatar_max_size,
                user_id=uploader_id,
            )
        except Exception:
            logger.exception(
                "sc_artist_avatar_upload_failed",
                artist_id=artist_id,
            )
            return
        artist.image_key = img_key
        await self._session.commit()
        try:
            from app.services.search_index_notify import (
                schedule_reindex_artist,
            )

            await schedule_reindex_artist(artist_id)
        except Exception:
            logger.warning(
                "sc_artist_avatar_reindex_failed",
                artist_id=artist_id,
            )

    async def search_users(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        if not self._client_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SoundCloud search is not configured",
            )
        q = (query or "").strip()
        if not q:
            return []
        q = q[:_MAX_SC_USER_SEARCH_QUERY_LEN]
        try:
            async with (
                soundcloud_slot(
                    timeout_seconds=(
                        settings.soundcloud_slot_acquire_timeout_seconds
                    ),
                ),
                self._sc_client() as client,
            ):
                r = await client.get(
                    f"{_SC_API_BASE}/search/users",
                    params={
                        "q": q,
                        "client_id": self._client_id,
                        "limit": min(limit, 50),
                        "offset": 0,
                        "linked_partitioning": 1,
                    },
                )
                if r.status_code == 401:
                    raise HTTPException(
                        status_code=(status.HTTP_503_SERVICE_UNAVAILABLE),
                        detail=(
                            "SoundCloud: неверный или устаревший "
                            "SC_CLIENT_ID. Обновите в .env и перезапустите."
                        ),
                    )
                r.raise_for_status()
                data = r.json()
        except SoundCloudSemaphoreTimeout as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SoundCloud is busy, retry later",
            ) from exc
        coll = data.get("collection", [])
        if not isinstance(coll, list):
            return []
        return [
            x for x in coll if isinstance(x, dict) and x.get("kind") == "user"
        ]

    async def _resolve_profile_permalink_to_user(
        self,
        permalink: str,
    ) -> tuple[int, str] | None:
        norm = normalize_soundcloud_permalink(permalink)
        if not norm:
            return None
        sc_url = f"https://soundcloud.com/{norm}"
        try:
            data = await self.resolve_url(sc_url)
        except HTTPException:
            return None
        if not isinstance(data, dict):
            return None
        if data.get("kind") != "user":
            return None
        uid = data.get("id")
        if not isinstance(uid, int):
            return None
        perm = data.get("permalink")
        pout = (
            normalize_soundcloud_permalink(str(perm))
            if isinstance(perm, str)
            else norm
        )
        if pout is None:
            pout = norm
        return uid, pout

    async def try_autofill_soundcloud_user_id_for_artist(
        self,
        artist_id: int,
    ) -> bool:
        repo = ArtistRepository(self._session)
        artist = await repo.get_by_id(artist_id)
        if artist is None:
            logger.warning(
                "sc_autofill_missing_artist",
                artist_id=artist_id,
            )
            return False
        if artist.soundcloud_user_id is not None:
            return True
        perm_candidates: list[str] = []
        seen: set[str] = set()
        ap = normalize_soundcloud_permalink(artist.soundcloud_permalink)
        if ap and ap not in seen:
            seen.add(ap)
            perm_candidates.append(ap)
        profiles = artist.source_profiles or []
        if isinstance(profiles, list):
            for item in profiles:
                if not isinstance(item, dict):
                    continue
                raw_u = item.get("source_page_url")
                if not isinstance(raw_u, str):
                    continue
                ext = extract_soundcloud_profile_permalink_from_url(
                    raw_u,
                )
                if ext and ext not in seen:
                    seen.add(ext)
                    perm_candidates.append(ext)
        for perm in perm_candidates:
            resolved = await self._resolve_profile_permalink_to_user(perm)
            if resolved is None:
                continue
            uid, canonical = resolved
            ok = await self.ensure_soundcloud_ids_for_artist(
                artist_id,
                uid,
                canonical,
            )
            if ok:
                logger.info(
                    "sc_autofill_from_profile",
                    artist_id=artist_id,
                    sc_user_id=uid,
                )
                return True
        name_q = (artist.name or "").strip()[:_MAX_SC_USER_SEARCH_QUERY_LEN]
        if not name_q:
            logger.info("sc_autofill_no_name", artist_id=artist_id)
            return False
        try:
            users = await self.search_users(name_q, limit=10)
        except HTTPException:
            logger.warning(
                "sc_autofill_search_users_failed",
                artist_id=artist_id,
            )
            return False
        if not users:
            logger.info(
                "sc_autofill_no_search_hits",
                artist_id=artist_id,
            )
            return False
        first = users[0]
        uid = first.get("id")
        if not isinstance(uid, int):
            return False
        perm_raw = first.get("permalink")
        pl = (
            normalize_soundcloud_permalink(str(perm_raw))
            if isinstance(perm_raw, str)
            else None
        )
        ok = await self.ensure_soundcloud_ids_for_artist(
            artist_id,
            int(uid),
            pl,
        )
        if ok:
            logger.warning(
                "sc_autofill_first_search_hit",
                artist_id=artist_id,
                sc_user_id=uid,
                artist_name=artist.name,
            )
        return ok

    async def import_or_get_track(
        self,
        sc_data: dict,
        uploader_id: int,
        is_public: bool = True,
        *,
        skip_background_lyrics: bool = False,
    ) -> Track:
        sc_url: str = sc_data.get("permalink_url", "")
        if sc_url:
            existing = await self._fetch_by_sc_url(sc_url)
            if existing:
                return existing

        async def _ingest_schedule(t: Track) -> None:
            from app.services.track_ingest_schedule_service import (
                schedule_new_track_background_jobs,
            )

            await schedule_new_track_background_jobs(
                self._session,
                t.id,
                skip_lyrics=skip_background_lyrics,
                catalog_payload={
                    "title": t.title,
                    "artist": t.artist,
                    "genre": t.genre,
                },
            )

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

        sc_id = sc_data.get("id")
        new_values = {
            "title": sc_data.get("title", "Unknown"),
            "artist": artist,
            "duration_seconds": duration_sec,
            "genre": sc_data.get("genre") or None,
            "description": sc_data.get("description") or None,
            "external_id": str(sc_id) if sc_id else None,
            "imported_from": "soundcloud",
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
                from app.services.search_index_notify import (
                    schedule_reindex_track,
                )

                await schedule_reindex_track(existing.id)
                return existing
            await self._session.refresh(track)
            logger.info(
                "sc_track_imported",
                sc_url=sc_url,
                track_id=track.id,
            )
            from app.services.search_index_notify import (
                schedule_reindex_track,
            )

            await schedule_reindex_track(track.id)
            await _ingest_schedule(track)
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
        from app.services.search_index_notify import (
            schedule_reindex_track,
        )

        await schedule_reindex_track(track.id)
        await _ingest_schedule(track)
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
