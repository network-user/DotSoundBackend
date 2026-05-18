from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

import structlog
from dotsound_private_core.services.radio_policy import (
    RADIO_DAILY_MATERIALIZE_CAP,
    cap_queue_ids,
    merge_dedup_ordered,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import AppSettings
from app.core.observability import radio_request_observed
from app.core.redis import get_redis_client
from app.models.track import Track
from app.models.user import User
from app.repositories.track import TrackRepository
from app.services.track_playback_health_service import (
    is_track_playback_suppressed,
)
from app.services.youtube_service import YouTubeService, _canonical_yt_url

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)
_RADIO_SKIP_GUARD_SECONDS = 1
_RADIO_LAST_QUEUE_TTL = 20


def _yt_mix_cache_key(seed_external_id: str) -> str:
    return f"radio:yt_mix:{seed_external_id}"


def _mat_key(user_id: int) -> str:
    return f"radio:mat:{user_id}:{date.today().isoformat()}"


class RadioService:
    def __init__(
        self,
        session: AsyncSession,
        settings: AppSettings,
    ) -> None:
        self._session = session
        self._settings = settings
        self._repo = TrackRepository(session)

    def _uploader_id(self, seed: Track, current: User | None) -> int:
        if current is not None:
            return int(current.id)
        if seed.uploaded_by_id is not None:
            return int(seed.uploaded_by_id)
        return 1

    async def _take_materialize_slot(self, user_id: int) -> bool:
        r = get_redis_client()
        key = _mat_key(user_id)
        n = await r.incr(key)
        if n == 1:
            await r.expire(key, 86400)
        if n > RADIO_DAILY_MATERIALIZE_CAP:
            await r.decr(key)
            return False
        return True

    @staticmethod
    def _yt_row_to_ydl_info(row: dict) -> dict[str, Any]:
        vid = (row.get("id") or "").strip()
        return {
            "id": vid,
            "title": (row.get("title") or "Unknown").strip(),
            "uploader": row.get("uploader") or "YouTube",
            "duration": row.get("duration"),
            "thumbnail": None,
            "thumbnails": [],
            "webpage_url": _canonical_yt_url(vid) if len(vid) == 11 else None,
        }

    async def _resolve_youtube_upstream(
        self,
        *,
        seed: Track,
        current: User | None,
        cap: int,
        up_cap: int,
    ) -> tuple[list[Track], str | None]:
        """Cache-aside + hard-budget wrapper around the YouTube-mix
        materialiser. The cold path runs the heavy yt-dlp / DB writes
        under ``asyncio.wait_for`` so the radio response never blocks
        the user for more than ``radio_yt_mix_budget_seconds``; the
        warm path serves stored track IDs from Redis in <1 ms.
        """
        redis = get_redis_client()
        cache_key = _yt_mix_cache_key(str(seed.external_id).strip())
        try:
            cached_raw = await redis.get(cache_key)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "radio_yt_mix_cache_read_failed", error=str(exc)
            )
            cached_raw = None
        if cached_raw:
            cached_ids = [
                int(x) for x in cached_raw.split(",") if x.isdigit()
            ]
            if cached_ids:
                rows = await self._repo.get_by_ids_preserve_order(cached_ids)
                if rows:
                    radio_request_observed(
                        surface="track_radio",
                        outcome="youtube_mix_cached",
                        queue_size=len(rows),
                    )
                    return rows, "youtube_mix_cached"

        budget = max(
            0.05, float(self._settings.radio_yt_mix_budget_seconds)
        )
        try:
            upstream, source_tag = await asyncio.wait_for(
                self._materialize_youtube_upstream(
                    seed=seed,
                    current=current,
                    cap=cap,
                    up_cap=up_cap,
                ),
                timeout=budget,
            )
        except TimeoutError:
            logger.info(
                "radio_yt_mix_budget_exceeded",
                seed_id=seed.id,
                budget_seconds=budget,
            )
            radio_request_observed(
                surface="track_radio",
                outcome="youtube_mix_pending",
                queue_size=0,
            )
            return [], "youtube_mix_pending"

        if upstream:
            ttl = max(
                30, int(self._settings.radio_yt_mix_cache_ttl_seconds)
            )
            try:
                await redis.setex(
                    cache_key,
                    ttl,
                    ",".join(str(t.id) for t in upstream),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "radio_yt_mix_cache_write_failed", error=str(exc)
                )
        return upstream, source_tag

    async def _materialize_youtube_upstream(
        self,
        *,
        seed: Track,
        current: User | None,
        cap: int,
        up_cap: int,
    ) -> tuple[list[Track], str | None]:
        """Original yt-dlp mix → import_or_get_track pipeline.
        Wrapped by :py:meth:`_resolve_youtube_upstream` for cache and
        wall-clock budget.
        """
        source_tag: str | None = "youtube_mix"
        uid = self._uploader_id(seed, current)
        yt = YouTubeService(self._session)
        try:
            mix_rows = await yt.list_mix_video_rows(
                str(seed.external_id).strip(),
                up_cap,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "radio_yt_mix_failed",
                error=str(exc),
            )
            mix_rows = []
        rows_to_process: list[dict] = mix_rows
        if not mix_rows:
            q = f"{seed.title} {seed.artist or ''}".strip()
            if q:
                try:
                    rows_to_process = await yt.search(q, limit=up_cap)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "radio_yt_search_failed",
                        error=str(exc),
                    )
                    rows_to_process = []
                source_tag = "youtube_search"

        upstream: list[Track] = []
        for row in rows_to_process:
            if len(upstream) >= cap:
                break
            if not await self._take_materialize_slot(uid):
                logger.info(
                    "radio_materialize_cap",
                    user_id=uid,
                )
                break
            try:
                if "video_id" in row and row.get("video_id"):
                    info = {
                        "id": (row.get("video_id") or "").strip(),
                        "title": row.get("title", "Unknown"),
                        "uploader": row.get("artist") or "YouTube",
                        "duration": row.get("duration_seconds"),
                        "thumbnail": None,
                        "thumbnails": [],
                        "webpage_url": row.get("watch_url"),
                    }
                else:
                    info = self._yt_row_to_ydl_info(row)
                if len((info.get("id") or "").strip()) != 11:
                    continue
                t = await yt.import_or_get_track(info, uploader_id=uid)
                upstream.append(t)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "radio_materialize_row_failed",
                    error=str(exc),
                )
        return upstream, source_tag

    async def build_queue(
        self,
        seed: Track,
        count: int,
        current: User | None,
    ) -> tuple[list[Track], str | None]:
        if current is not None:
            redis = get_redis_client()
            guard_key = (
                f"radio:guard:{current.id}:{seed.id}"
            )
            last_key = f"radio:last:{current.id}:{seed.id}"
            can_fetch = await redis.set(
                guard_key,
                "1",
                ex=_RADIO_SKIP_GUARD_SECONDS,
                nx=True,
            )
            if not can_fetch:
                cached_ids = await redis.get(last_key)
                if cached_ids:
                    tracks = await self._repo.get_by_ids_preserve_order(
                        [int(tid) for tid in cached_ids.split(",") if tid]
                    )
                    radio_request_observed(
                        surface="track_radio",
                        outcome="guarded",
                        queue_size=len(tracks),
                        guard_hit=True,
                    )
                    return tracks, "guarded"

        if not self._settings.radio_enabled:
            rows = await self._repo.get_next_tracks(seed.id, count)
            if current is not None and rows:
                redis = get_redis_client()
                await redis.setex(
                    f"radio:last:{current.id}:{seed.id}",
                    _RADIO_LAST_QUEUE_TTL,
                    ",".join(str(t.id) for t in rows),
                )
            radio_request_observed(
                surface="track_radio",
                outcome="catalog",
                queue_size=len(rows),
            )
            return rows, "catalog"

        cap = min(
            count,
            self._settings.radio_max_suggestions,
        )
        base = await self._repo.get_next_tracks(seed.id, cap)
        base_ids = [t.id for t in base]

        upstream: list[Track] = []
        source_tag: str | None = None
        up_cap = min(cap, RADIO_DAILY_MATERIALIZE_CAP)
        if (
            self._settings.radio_youtube_mix_enabled
            and self._settings.youtube_enabled
            and seed.source_platform == "youtube"
            and seed.external_id
        ):
            upstream, source_tag = await self._resolve_youtube_upstream(
                seed=seed,
                current=current,
                cap=cap,
                up_cap=up_cap,
            )

        upstream = [
            t for t in upstream
            if not is_track_playback_suppressed(t)
        ]
        merged = merge_dedup_ordered(
            base_ids,
            [t.id for t in upstream],
        )
        ids = cap_queue_ids(merged, cap)
        if not ids:
            radio_request_observed(
                surface="track_radio",
                outcome="empty",
                queue_size=0,
            )
            return [], source_tag
        out = await self._repo.get_by_ids_preserve_order(ids)
        if current is not None and out:
            redis = get_redis_client()
            await redis.setex(
                f"radio:last:{current.id}:{seed.id}",
                _RADIO_LAST_QUEUE_TTL,
                ",".join(str(t.id) for t in out),
            )
        radio_request_observed(
            surface="track_radio",
            outcome=source_tag or "catalog",
            queue_size=len(out),
        )
        return out, source_tag
