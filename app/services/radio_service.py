from __future__ import annotations

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
from app.core.redis import get_redis_client
from app.models.track import Track
from app.models.user import User
from app.repositories.track import TrackRepository
from app.services.youtube_service import YouTubeService, _canonical_yt_url

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


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

    async def build_queue(
        self,
        seed: Track,
        count: int,
        current: User | None,
    ) -> tuple[list[Track], str | None]:
        if not self._settings.radio_enabled:
            rows = await self._repo.get_next_tracks(seed.id, count)
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
            and seed.source_platform == "youtube"
            and seed.external_id
        ):
            source_tag = "youtube_mix"
            uid = self._uploader_id(seed, current)
            yt = YouTubeService(self._session)
            mix_rows = await yt.list_mix_video_rows(
                str(seed.external_id).strip(),
                up_cap,
            )
            rows_to_process: list[dict] = mix_rows
            if not mix_rows:
                q = f"{seed.title} {seed.artist or ''}".strip()
                if q:
                    try:
                        rows_to_process = await yt.search(q, limit=up_cap)
                    except Exception as exc:
                        logger.warning(
                            "radio_yt_search_failed",
                            error=str(exc),
                        )
                        rows_to_process = []
                    source_tag = "youtube_search"

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
                except Exception as exc:
                    logger.warning(
                        "radio_materialize_row_failed",
                        error=str(exc),
                    )

        merged = merge_dedup_ordered(
            base_ids,
            [t.id for t in upstream],
        )
        ids = cap_queue_ids(merged, cap)
        if not ids:
            return [], source_tag
        out = await self._repo.get_by_ids_preserve_order(ids)
        return out, source_tag
