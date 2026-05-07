from datetime import UTC

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.lyrics import TrackLyrics
from app.models.track import Track
from app.models.lyrics_translation import (
    TrackLyricsTranslation,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class LyricsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_track_id(self, track_id: int) -> TrackLyrics | None:
        result = await self._session.execute(
            select(TrackLyrics)
            .options(selectinload(TrackLyrics.translations))
            .where(TrackLyrics.track_id == track_id)
        )
        return result.scalar_one_or_none()

    async def has_nonempty_plain_text(self, track_id: int) -> bool:
        result = await self._session.execute(
            select(func.trim(TrackLyrics.plain_text)).where(
                TrackLyrics.track_id == track_id,
            ),
        )
        raw = result.scalar_one_or_none()
        return bool(raw and raw.strip())

    async def nonempty_plain_track_ids(
        self, track_ids: list[int],
    ) -> set[int]:
        if not track_ids:
            return set()
        stripped = func.trim(func.coalesce(TrackLyrics.plain_text, ""))
        result = await self._session.execute(
            select(TrackLyrics.track_id).where(
                TrackLyrics.track_id.in_(track_ids),
                stripped != "",
            ),
        )
        return set(int(r) for r in result.scalars().all())

    async def create_or_update(
        self,
        track_id: int,
        plain_text: str,
        source: str = "manual",
        synced_lines: list[dict] | None = None,
        sync_quality: str | None = None,
        sync_profile: str | None = None,
        source_name: str | None = None,
        sync_source_name: str | None = None,
    ) -> TrackLyrics:
        from datetime import datetime

        now = datetime.now(UTC)
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
            update_values["sync_source_name"] = (
                sync_source_name if synced_lines else None
            )
        elif source == "manual":
            update_values["sync_quality"] = None
            update_values["sync_profile"] = None
            update_values["sync_source_name"] = None

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
                sync_source_name=(sync_source_name if synced_lines else None),
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
        logger.debug("db_lyrics_upserted", track_id=track_id)
        if plain_text.strip():
            row = await self._session.get(Track, track_id)
            if row is not None:
                row.lyrics_catalog_miss_at = None
            try:
                from app.services.lyrics_derived_genre_mood_service import (
                    apply_after_lyrics_saved,
                )

                await apply_after_lyrics_saved(
                    self._session,
                    track_id,
                    plain_text,
                )
            except Exception:
                logger.warning(
                    "lyrics_derived_genre_mood_failed",
                    track_id=track_id,
                    exc_info=True,
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
        logger.debug("db_lyrics_sync_updated", track_id=track_id)
        return existing

    async def delete_by_track_id(self, track_id: int) -> bool:
        result = await self._session.execute(
            delete(TrackLyrics).where(TrackLyrics.track_id == track_id)
        )
        removed = result.rowcount > 0
        logger.debug(
            "db_lyrics_deleted",
            track_id=track_id,
            found=removed,
        )
        return removed

    async def list_translations(
        self, track_lyrics_id: int
    ) -> list[TrackLyricsTranslation]:
        result = await self._session.execute(
            select(TrackLyricsTranslation)
            .where(
                TrackLyricsTranslation.track_lyrics_id
                == track_lyrics_id
            )
            .order_by(TrackLyricsTranslation.language_code.asc())
        )
        return list(result.scalars().all())

    async def upsert_translation(
        self,
        track_lyrics_id: int,
        language_code: str,
        translated_text: str,
    ) -> TrackLyricsTranslation:
        from datetime import datetime

        normalized_code = language_code.strip().lower()
        now = datetime.now(UTC)
        stmt = (
            insert(TrackLyricsTranslation)
            .values(
                track_lyrics_id=track_lyrics_id,
                language_code=normalized_code,
                translated_text=translated_text,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                constraint="uq_track_lyrics_translations_language",
                set_={
                    "translated_text": translated_text,
                    "updated_at": now,
                },
            )
            .returning(TrackLyricsTranslation)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def delete_translation(
        self,
        track_lyrics_id: int,
        language_code: str,
    ) -> bool:
        result = await self._session.execute(
            delete(TrackLyricsTranslation).where(
                TrackLyricsTranslation.track_lyrics_id
                == track_lyrics_id,
                TrackLyricsTranslation.language_code
                == language_code.strip().lower(),
            )
        )
        return result.rowcount > 0
