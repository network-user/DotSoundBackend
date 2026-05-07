import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.models.user import User
from app.repositories.track import TrackRepository
from app.repositories.user import UserRepository
from app.repositories.user_track_library import (
    UserTrackLibraryRepository,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class TrackService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = TrackRepository(session)
        self._user_repo = UserRepository(session)
        self._library_repo = UserTrackLibraryRepository(session)

    async def _resolve_user(self, user_id: int) -> User:
        user = await self._user_repo.get_by_id(user_id)
        if not user:
            user = await self._user_repo.get_by_telegram_id(user_id)

        if not user:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return user

    async def list_tracks(
        self,
        page: int = 1,
        size: int = 20,
        playable_only: bool = False,
    ) -> tuple[list[Track], int]:
        offset = (page - 1) * size
        tracks, total = await self._repo.list_active(
            offset=offset,
            limit=size,
            playable_only=playable_only,
        )
        logger.info(
            "tracks_listed",
            page=page,
            size=size,
            total=total,
            returned=len(tracks),
        )
        return tracks, total

    async def get_track(self, track_id: int) -> Track | None:
        track = await self._repo.get_by_id(track_id)
        if not track or not track.is_active:
            logger.warning("track_not_found", track_id=track_id)
            return None
        logger.debug("track_fetched", track_id=track_id)
        return track

    async def search(
        self,
        query: str,
        page: int = 1,
        size: int = 20,
        playable_only: bool = False,
        genre_filter: str | None = None,
    ) -> tuple[list[Track], int]:
        from app.config import settings
        from app.core.observability import (
            elasticsearch_query_observed,
        )
        from app.search.es_client import es_available
        from app.services import search_query_service

        use_es = bool(
            settings.elasticsearch_enabled
            and (settings.elasticsearch_url or "").strip()
            and es_available()
        )
        if use_es and not genre_filter:
            es_hits = await search_query_service.es_search_tracks(
                query,
                page=page,
                size=size,
                playable_only=playable_only,
            )
            if es_hits is not None:
                ids, total = es_hits
                if ids:
                    elasticsearch_query_observed(
                        op="track_search", outcome="es_ok"
                    )
                    orm = await self._repo.get_by_ids_preserve_order(ids)
                    if len(orm) != len(ids):
                        logger.info(
                            "es_sql_hydrate_mismatch",
                            want=len(ids),
                            got=len(orm),
                        )
                    logger.info(
                        "tracks_searched",
                        source="elasticsearch",
                        query=query,
                        page=page,
                        total=total,
                    )
                    return orm, total
                if (
                    total == 0
                    and settings.elasticsearch_fallback_to_postgres_on_zero
                ):
                    elasticsearch_query_observed(
                        op="track_search", outcome="pg_fallback"
                    )
                else:
                    elasticsearch_query_observed(
                        op="track_search", outcome="es_ok"
                    )
                    logger.info(
                        "tracks_searched",
                        source="elasticsearch",
                        query=query,
                        page=page,
                        total=total,
                    )
                    return [], total
            else:
                elasticsearch_query_observed(
                    op="track_search", outcome="pg_fallback"
                )
        offset = (page - 1) * size
        tracks, total = await self._repo.search(
            query=query,
            offset=offset,
            limit=size,
            playable_only=playable_only,
            genre_filter=genre_filter,
        )
        logger.info(
            "tracks_searched",
            source="postgresql",
            query=query,
            page=page,
            total=total,
        )
        return tracks, total

    async def list_by_user(
        self,
        user_id: int,
        page: int = 1,
        size: int = 50,
        playable_only: bool = False,
    ) -> tuple[list[Track], int]:
        offset = (page - 1) * size
        return await self._repo.list_by_user(
            user_id=user_id,
            offset=offset,
            limit=size,
            playable_only=playable_only,
        )

    async def list_library(
        self,
        user_id: int,
        page: int = 1,
        size: int = 50,
        playable_only: bool = False,
    ) -> tuple[list[Track], int]:
        user = await self._resolve_user(user_id)
        offset = (page - 1) * size
        return await self._library_repo.list_by_user(
            user_id=user.id,
            offset=offset,
            limit=size,
            playable_only=playable_only,
        )

    async def list_by_followed_artists(
        self,
        user_id: int,
        page: int = 1,
        size: int = 20,
        playable_only: bool = False,
    ) -> tuple[list[Track], int]:
        from app.repositories.artist_follow import ArtistFollowRepository

        follow_repo = ArtistFollowRepository(self._session)
        artist_ids = await follow_repo.list_followed_artist_ids(user_id)
        if not artist_ids:
            return [], 0
        offset = (page - 1) * size
        return await self._repo.list_by_artist_ids(
            artist_ids=artist_ids,
            offset=offset,
            limit=size,
            playable_only=playable_only,
        )

    async def update_visibility(
        self, track_id: int, user_id: int, is_public: bool
    ) -> Track | None:
        out = await self._repo.update_visibility(
            track_id=track_id,
            user_id=user_id,
            is_public=is_public,
        )
        if out:
            from app.services.search_index_notify import (
                schedule_reindex_track,
            )

            await schedule_reindex_track(out.id)
        return out

    async def update_track(
        self,
        track_id: int,
        user_id: int,
        **fields: object,
    ) -> Track | None:
        out = await self._repo.update_track(
            track_id=track_id,
            user_id=user_id,
            **fields,
        )
        if out:
            from app.services.search_index_notify import (
                schedule_reindex_track,
            )

            await schedule_reindex_track(out.id)
        return out

    async def admin_update_track(
        self,
        track_id: int,
        **fields: object,
    ) -> Track | None:
        out = await self._repo.admin_update_track(
            track_id=track_id,
            **fields,
        )
        if out:
            from app.services.search_index_notify import (
                schedule_reindex_track,
            )

            await schedule_reindex_track(out.id)
        return out

    async def delete_by_owner(
        self, track_id: int, user_id: int
    ) -> Track | None:
        out = await self._repo.delete_by_owner(
            track_id=track_id, user_id=user_id
        )
        if out is not None:
            from app.services.search_index_notify import (
                schedule_delete_track,
            )

            await schedule_delete_track(track_id)
        return out

    async def list_public_by_user(
        self,
        user_id: int,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[Track], int]:
        user = await self._resolve_user(user_id)
        offset = (page - 1) * size
        return await self._repo.list_public_by_user(
            user_id=user.id, offset=offset, limit=size
        )

    async def get_genres(self) -> list[str]:
        return await self._repo.get_unique_genres()
