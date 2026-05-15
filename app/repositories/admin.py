"""Repository for admin-only DB queries.

This file replaces the inline ``select(...)`` calls that used to
live inside ``app/api/v1/admin/{tracks,users,complaints}.py``,
closing the tech debt item in AGENTS.md.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.models.artist import TrackArtist
from app.models.complaint import Complaint
from app.models.lyrics import TrackLyrics
from app.models.track import Track
from app.models.track_playback_failure_event import (
    TrackPlaybackFailureEvent,
)
from app.models.user import User
from app.repositories.track import TrackRepository


class AdminRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _apply_track_list_filters(
        self,
        query: Select,
        *,
        is_active: bool | None,
        without_lyrics: bool,
        lyrics_catalog_miss_only: bool,
        search: str | None,
        for_playlist_owner_id: int | None,
        playable_only: bool,
    ) -> Select:
        if lyrics_catalog_miss_only:
            query = query.where(
                Track.lyrics_catalog_miss_at.isnot(None),
            )
        elif without_lyrics:
            query = query.outerjoin(
                TrackLyrics, TrackLyrics.track_id == Track.id
            ).where(TrackLyrics.id.is_(None))
        if is_active is not None:
            query = query.where(Track.is_active.is_(is_active))
        if for_playlist_owner_id is not None:
            tr = TrackRepository
            pub = (
                Track.is_active.is_(True)
                & Track.is_public.is_(True)
                & tr._exclude_hidden_sources()
                & tr._playback_listing_allowed()
            )
            own = (
                Track.is_active.is_(True)
                & (Track.uploaded_by_id == for_playlist_owner_id)
                & tr._exclude_hidden_sources()
                & tr._playback_listing_allowed()
            )
            if playable_only:
                playable = tr._playable_filter()
                pub = and_(pub, playable)
                own = and_(own, playable)
            query = query.where(or_(pub, own))
        elif playable_only:
            tr = TrackRepository
            query = query.where(
                and_(
                    Track.is_active.is_(True),
                    tr._exclude_hidden_sources(),
                    tr._playback_listing_allowed(),
                    tr._playable_filter(),
                )
            )
        if search:
            pattern = f"%{search}%"
            query = query.where(
                Track.title.ilike(pattern) | Track.artist.ilike(pattern)
            )
        return query

    async def list_tracks(
        self,
        *,
        page: int = 1,
        size: int = 20,
        is_active: bool | None = None,
        without_lyrics: bool = False,
        lyrics_catalog_miss_only: bool = False,
        search: str | None = None,
        for_playlist_owner_id: int | None = None,
        playable_only: bool = False,
    ) -> tuple[list[Track], int]:
        query = self._apply_track_list_filters(
            select(Track),
            is_active=is_active,
            without_lyrics=without_lyrics,
            lyrics_catalog_miss_only=lyrics_catalog_miss_only,
            search=search,
            for_playlist_owner_id=for_playlist_owner_id,
            playable_only=playable_only,
        )
        count_query = self._apply_track_list_filters(
            select(func.count(Track.id)),
            is_active=is_active,
            without_lyrics=without_lyrics,
            lyrics_catalog_miss_only=lyrics_catalog_miss_only,
            search=search,
            for_playlist_owner_id=for_playlist_owner_id,
            playable_only=playable_only,
        )
        query = (
            query.order_by(Track.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        result = await self._session.execute(query)
        rows = list(result.scalars().all())
        total_result = await self._session.execute(count_query)
        return rows, int(total_result.scalar_one())

    async def list_track_ids(
        self,
        *,
        is_active: bool | None = None,
        without_lyrics: bool = False,
        lyrics_catalog_miss_only: bool = False,
        search: str | None = None,
        for_playlist_owner_id: int | None = None,
        playable_only: bool = False,
    ) -> tuple[list[int], int]:
        query = self._apply_track_list_filters(
            select(Track.id),
            is_active=is_active,
            without_lyrics=without_lyrics,
            lyrics_catalog_miss_only=lyrics_catalog_miss_only,
            search=search,
            for_playlist_owner_id=for_playlist_owner_id,
            playable_only=playable_only,
        ).order_by(Track.created_at.desc())
        count_query = self._apply_track_list_filters(
            select(func.count(Track.id)),
            is_active=is_active,
            without_lyrics=without_lyrics,
            lyrics_catalog_miss_only=lyrics_catalog_miss_only,
            search=search,
            for_playlist_owner_id=for_playlist_owner_id,
            playable_only=playable_only,
        )
        rows = await self._session.execute(query)
        total = await self._session.execute(count_query)
        return [int(track_id) for track_id in rows.scalars().all()], int(
            total.scalar_one()
        )

    async def list_tracks_playback_unavailable(
        self,
        *,
        page: int = 1,
        size: int = 20,
        search: str | None = None,
    ) -> tuple[list[Track], int]:
        q = select(Track).where(
            Track.playback_last_failure_at.isnot(None),
        )
        cq = select(func.count(Track.id)).where(
            Track.playback_last_failure_at.isnot(None),
        )
        if search:
            pattern = f"%{search}%"
            cond = Track.title.ilike(pattern) | Track.artist.ilike(pattern)
            q = q.where(cond)
            cq = cq.where(cond)
        q = (
            q.order_by(desc(Track.playback_last_failure_at))
            .offset((page - 1) * size)
            .limit(size)
        )
        result = await self._session.execute(q)
        rows = list(result.scalars().all())
        total_result = await self._session.execute(cq)
        return rows, int(total_result.scalar_one())

    async def list_track_ids_playback_unavailable(
        self,
        *,
        search: str | None = None,
    ) -> tuple[list[int], int]:
        q = select(Track.id).where(
            Track.playback_last_failure_at.isnot(None),
        )
        cq = select(func.count(Track.id)).where(
            Track.playback_last_failure_at.isnot(None),
        )
        if search:
            pattern = f"%{search}%"
            cond = Track.title.ilike(pattern) | Track.artist.ilike(pattern)
            q = q.where(cond)
            cq = cq.where(cond)
        q = q.order_by(desc(Track.playback_last_failure_at))
        rows = await self._session.execute(q)
        total_result = await self._session.execute(cq)
        return [int(track_id) for track_id in rows.scalars().all()], int(
            total_result.scalar_one()
        )

    async def list_tracks_playback_suppressed(
        self,
        *,
        page: int = 1,
        size: int = 20,
        search: str | None = None,
    ) -> tuple[list[Track], int]:
        q = select(Track).where(
            Track.playback_suppressed_until.isnot(None),
            Track.playback_suppressed_until > func.now(),
        )
        cq = select(func.count(Track.id)).where(
            Track.playback_suppressed_until.isnot(None),
            Track.playback_suppressed_until > func.now(),
        )
        if search:
            pattern = f"%{search}%"
            cond = Track.title.ilike(pattern) | Track.artist.ilike(pattern)
            q = q.where(cond)
            cq = cq.where(cond)
        q = (
            q.order_by(desc(Track.playback_suppressed_until))
            .offset((page - 1) * size)
            .limit(size)
        )
        result = await self._session.execute(q)
        rows = list(result.scalars().all())
        total_result = await self._session.execute(cq)
        return rows, int(total_result.scalar_one())

    async def list_track_ids_playback_suppressed(
        self,
        *,
        search: str | None = None,
    ) -> tuple[list[int], int]:
        q = select(Track.id).where(
            Track.playback_suppressed_until.isnot(None),
            Track.playback_suppressed_until > func.now(),
        )
        cq = select(func.count(Track.id)).where(
            Track.playback_suppressed_until.isnot(None),
            Track.playback_suppressed_until > func.now(),
        )
        if search:
            pattern = f"%{search}%"
            cond = Track.title.ilike(pattern) | Track.artist.ilike(pattern)
            q = q.where(cond)
            cq = cq.where(cond)
        q = q.order_by(desc(Track.playback_suppressed_until))
        rows = await self._session.execute(q)
        total_result = await self._session.execute(cq)
        return [int(track_id) for track_id in rows.scalars().all()], int(
            total_result.scalar_one()
        )

    async def latest_track_playback_failure_events(
        self,
        track_ids: list[int],
    ) -> dict[int, TrackPlaybackFailureEvent]:
        if not track_ids:
            return {}
        q = (
            select(TrackPlaybackFailureEvent)
            .where(TrackPlaybackFailureEvent.track_id.in_(track_ids))
            .order_by(
                TrackPlaybackFailureEvent.track_id,
                desc(TrackPlaybackFailureEvent.created_at),
                desc(TrackPlaybackFailureEvent.id),
            )
        )
        result = await self._session.execute(q)
        latest: dict[int, TrackPlaybackFailureEvent] = {}
        for event in result.scalars().all():
            if event.track_id not in latest:
                latest[event.track_id] = event
        return latest

    async def list_tracks_for_artist(
        self,
        artist_id: int,
        *,
        page: int = 1,
        size: int = 20,
        search: str | None = None,
    ) -> tuple[list[Track], int]:
        base_join = TrackArtist.track_id == Track.id
        query = (
            select(Track)
            .join(TrackArtist, base_join)
            .where(TrackArtist.artist_id == artist_id)
        )
        count_query = (
            select(func.count(Track.id))
            .select_from(Track)
            .join(TrackArtist, base_join)
            .where(TrackArtist.artist_id == artist_id)
        )
        if search:
            pattern = f"%{search}%"
            cond = Track.title.ilike(pattern) | Track.artist.ilike(pattern)
            query = query.where(cond)
            count_query = count_query.where(cond)
        query = (
            query.order_by(desc(Track.created_at))
            .offset((page - 1) * size)
            .limit(size)
        )
        result = await self._session.execute(query)
        rows = list(result.scalars().all())
        total_result = await self._session.execute(count_query)
        return rows, int(total_result.scalar_one())

    async def get_track(self, track_id: int) -> Track | None:
        result = await self._session.execute(
            select(Track).where(Track.id == track_id)
        )
        return result.scalar_one_or_none()

    async def list_users(
        self,
        *,
        page: int = 1,
        size: int = 20,
        is_active: bool | None = None,
        is_admin: bool | None = None,
        search: str | None = None,
    ) -> tuple[list[User], int]:
        query = select(User)
        count_query = select(func.count(User.id))
        if is_active is not None:
            query = query.where(User.is_active.is_(is_active))
            count_query = count_query.where(User.is_active.is_(is_active))
        if is_admin is not None:
            query = query.where(User.is_admin.is_(is_admin))
            count_query = count_query.where(User.is_admin.is_(is_admin))
        if search:
            pattern = f"%{search}%"
            cond = or_(
                User.username.ilike(pattern),
                User.email.ilike(pattern),
                User.first_name.ilike(pattern),
                User.last_name.ilike(pattern),
                User.display_name.ilike(pattern),
            )
            query = query.where(cond)
            count_query = count_query.where(cond)
        query = (
            query.order_by(desc(User.created_at))
            .offset((page - 1) * size)
            .limit(size)
        )
        result = await self._session.execute(query)
        rows = list(result.scalars().all())
        total_result = await self._session.execute(count_query)
        return rows, int(total_result.scalar_one())

    async def list_deleted_users(
        self,
        *,
        page: int = 1,
        size: int = 25,
        search: str | None = None,
    ) -> tuple[list[User], int]:
        condition = User.deleted_at.is_not(None)
        if search:
            pattern = f"%{search.strip()}%"
            cond = or_(
                User.username.ilike(pattern),
                User.email.ilike(pattern),
                User.first_name.ilike(pattern),
                User.last_name.ilike(pattern),
                User.display_name.ilike(pattern),
            )
            condition = condition & cond
        total_q = select(func.count(User.id)).where(condition)
        total = int(
            (await self._session.execute(total_q)).scalar_one()
        )
        rows = await self._session.execute(
            select(User)
            .where(condition)
            .order_by(desc(User.deleted_at))
            .offset((page - 1) * size)
            .limit(size)
        )
        return list(rows.scalars().all()), total

    async def get_user(self, user_id: int) -> User | None:
        result = await self._session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_complaints(
        self,
        *,
        page: int = 1,
        size: int = 20,
        unresolved_only: bool = False,
    ) -> tuple[list[Complaint], int]:
        query = select(Complaint)
        count_query = select(func.count(Complaint.id))
        if unresolved_only:
            query = query.where(Complaint.is_resolved.is_(False))
            count_query = count_query.where(Complaint.is_resolved.is_(False))
        query = (
            query.order_by(desc(Complaint.created_at))
            .offset((page - 1) * size)
            .limit(size)
        )
        result = await self._session.execute(query)
        rows = list(result.scalars().all())
        total_result = await self._session.execute(count_query)
        return rows, int(total_result.scalar_one())

    async def get_complaint(self, complaint_id: int) -> Complaint | None:
        result = await self._session.execute(
            select(Complaint).where(Complaint.id == complaint_id)
        )
        return result.scalar_one_or_none()

    async def get_popular_genres(
        self, limit: int = 20
    ) -> list[dict[str, Any]]:
        result = await self._session.execute(
            select(
                Track.genre,
                func.count(Track.id).label("count"),
            )
            .where(
                Track.genre.isnot(None),
                Track.genre != "",
                Track.is_active.is_(True),
                Track.is_public.is_(True),
            )
            .group_by(Track.genre)
            .order_by(desc("count"))
            .limit(limit)
        )
        return [
            {
                "genre": str(row[0]),
                "count": int(row[1]),
            }
            for row in result.all()
        ]
