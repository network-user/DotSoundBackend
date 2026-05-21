from datetime import datetime

import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.repositories.dislike import DislikeRepository
from app.repositories.like import LikeRepository
from app.repositories.track import TrackRepository
from app.repositories.user import UserRepository
from app.services.playback_variant_service import PlaybackVariantService

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class LikeService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = LikeRepository(session)
        self._track_repo = TrackRepository(session)
        self._user_repo = UserRepository(session)
        self._dislike_repo = DislikeRepository(session)
        self._session = session

    async def toggle(
        self, user_id: int, track_id: int
    ) -> tuple[bool, list[int]]:
        user = await self._user_repo.get_by_id(user_id)
        if not user:
            user = await self._user_repo.get_by_telegram_id(user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        resolved_user_id = user.id

        track = await self._track_repo.get_by_id(track_id)
        if not track or not track.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Track not found",
            )

        pvs = PlaybackVariantService(self._session)
        variant_ids = await pvs.resolve_variant_track_ids(track)

        any_liked = await self._repo.exists_any_for_user_track_ids(
            resolved_user_id,
            variant_ids,
        )
        if any_liked:
            for vid in variant_ids:
                await self._repo.remove(resolved_user_id, vid)
            liked = False
        else:
            for vid in variant_ids:
                await self._dislike_repo.remove(resolved_user_id, vid)
            for vid in variant_ids:
                await self._repo.add_idempotent(resolved_user_id, vid)
            liked = True

        logger.info(
            "like_toggled",
            user_id=resolved_user_id,
            track_id=track_id,
            liked=liked,
            variant_count=len(variant_ids),
        )
        return liked, variant_ids

    async def collapse_liked_rows(
        self,
        rows: list[tuple[Track, datetime]],
        sort_order: str = "newest",
    ) -> list[tuple[Track, datetime]]:
        if not rows:
            return []
        pvs = PlaybackVariantService(self._session)
        by_group: dict[frozenset[int], tuple[Track, datetime]] = {}
        for tr, la in rows:
            g = frozenset(await pvs.resolve_variant_track_ids(tr))
            cur = by_group.get(g)
            if (
                cur is None
                or (sort_order == "newest" and la > cur[1])
                or (sort_order == "oldest" and la < cur[1])
            ):
                by_group[g] = (tr, la)
        out = list(by_group.values())
        if sort_order == "newest":
            out.sort(key=lambda x: x[1], reverse=True)
        elif sort_order == "oldest":
            out.sort(key=lambda x: x[1])
        return out

    async def list_liked(
        self,
        user_id: int,
        page: int = 1,
        size: int = 20,
        source_filter: str | None = None,
        sort_order: str = "newest",
    ) -> tuple[list[tuple[Track, datetime]], int]:
        user = await self._user_repo.get_by_id(user_id)
        if not user:
            user = await self._user_repo.get_by_telegram_id(user_id)

        if not user:
            return [], 0

        offset = (page - 1) * size
        rows, total = await self._repo.list_liked_tracks(
            user_id=user.id,
            offset=offset,
            limit=size,
            source_filter=source_filter,
            sort_order=sort_order,
        )
        collapsed = await self.collapse_liked_rows(rows, sort_order)
        logger.info(
            "liked_tracks_listed",
            user_id=user.id,
            total=total,
        )
        return collapsed, total

    async def list_liked_queue(
        self,
        user_id: int,
        current_track_id: int,
        size: int = 80,
        source_filter: str | None = None,
        sort_order: str = "newest",
        shuffle: bool = False,
        exclude_ids: set[int] | None = None,
    ) -> list[Track]:
        user = await self._user_repo.get_by_id(user_id)
        if not user:
            user = await self._user_repo.get_by_telegram_id(user_id)
        if not user:
            return []
        rows = await self._repo.list_liked_queue(
            user_id=user.id,
            current_track_id=current_track_id,
            limit=size,
            source_filter=source_filter,
            sort_order=sort_order,
            shuffle=shuffle,
            exclude_ids=exclude_ids,
        )
        collapse_order = "shuffle" if shuffle else sort_order
        collapsed = await self.collapse_liked_rows(rows, collapse_order)
        return [track for track, _liked_at in collapsed[:size]]

    async def is_liked(
        self, user_id: int, track_id: int
    ) -> bool:
        user = await self._user_repo.get_by_id(user_id)
        if not user:
            user = await self._user_repo.get_by_telegram_id(user_id)
        if not user:
            return False
        track = await self._track_repo.get_by_id(track_id)
        if not track:
            return False
        pvs = PlaybackVariantService(self._session)
        variant_ids = await pvs.resolve_variant_track_ids(track)
        return await self._repo.exists_any_for_user_track_ids(
            user.id,
            variant_ids,
        )
