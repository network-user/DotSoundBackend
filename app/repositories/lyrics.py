import structlog
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lyrics import TrackLyrics

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class LyricsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_track_id(
        self, track_id: int
    ) -> TrackLyrics | None:
        result = await self._session.execute(
            select(TrackLyrics).where(
                TrackLyrics.track_id == track_id
            )
        )
        return result.scalar_one_or_none()

    async def create_or_update(
        self,
        track_id: int,
        plain_text: str,
        source: str = "manual",
        synced_lines: list[dict] | None = None,
        sync_quality: str | None = None,
        sync_profile: str | None = None,
        source_name: str | None = None,
    ) -> TrackLyrics:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        update_values: dict = {
            "plain_text": plain_text,
            "source": source,
            "source_name": source_name,
            "updated_at": now,
        }
        if synced_lines is not None:
            update_values["synced_lines"] = synced_lines
        elif source == "manual":
            update_values["synced_lines"] = None

        if source == "auto":
            update_values["sync_quality"] = sync_quality
            update_values["sync_profile"] = sync_profile
        elif source == "manual":
            update_values["sync_quality"] = None
            update_values["sync_profile"] = None

        stmt = (
            insert(TrackLyrics)
            .values(
                track_id=track_id,
                plain_text=plain_text,
                source=source,
                source_name=source_name,
                synced_lines=synced_lines,
                sync_quality=sync_quality,
                sync_profile=sync_profile,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["track_id"],
                set_=update_values,
            )
            .returning(TrackLyrics)
        )
        result = await self._session.execute(stmt)
        lyrics = result.scalar_one()
        logger.debug(
            "db_lyrics_upserted", track_id=track_id
        )
        return lyrics

    async def update_sync(
        self, track_id: int, synced_lines: list[dict]
    ) -> TrackLyrics | None:
        existing = await self.get_by_track_id(track_id)
        if not existing:
            return None
        existing.synced_lines = synced_lines
        await self._session.flush()
        await self._session.refresh(existing)
        logger.debug(
            "db_lyrics_sync_updated", track_id=track_id
        )
        return existing

    async def delete_by_track_id(
        self, track_id: int
    ) -> bool:
        result = await self._session.execute(
            delete(TrackLyrics).where(
                TrackLyrics.track_id == track_id
            )
        )
        removed = result.rowcount > 0
        logger.debug(
            "db_lyrics_deleted",
            track_id=track_id,
            found=removed,
        )
        return removed
