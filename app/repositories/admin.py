"""Repository for admin-only DB queries.

This file replaces the inline ``select(...)`` calls that used to
live inside ``app/api/v1/admin/{tracks,users,complaints}.py``,
closing the tech debt item in AGENTS.md.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artist import TrackArtist
from app.models.complaint import Complaint
from app.models.lyrics import TrackLyrics
from app.models.track import Track
from app.models.user import User


class AdminRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_tracks(
        self,
        *,
        page: int = 1,
        size: int = 20,
        is_active: bool | None = None,
        without_lyrics: bool = False,
        search: str | None = None,
    ) -> tuple[list[Track], int]:
        query = select(Track)
        count_query = select(func.count(Track.id))
        if without_lyrics:
            query = query.outerjoin(
                TrackLyrics, TrackLyrics.track_id == Track.id
            ).where(TrackLyrics.id.is_(None))
            count_query = count_query.outerjoin(
                TrackLyrics, TrackLyrics.track_id == Track.id
            ).where(TrackLyrics.id.is_(None))
        if is_active is not None:
            query = query.where(Track.is_active.is_(is_active))
            count_query = count_query.where(Track.is_active.is_(is_active))
        if search:
            pattern = f"%{search}%"
            cond = Track.title.ilike(pattern) | Track.artist.ilike(pattern)
            query = query.where(cond)
            count_query = count_query.where(cond)
        query = (
            query.order_by(Track.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        result = await self._session.execute(query)
        rows = list(result.scalars().all())
        total_result = await self._session.execute(count_query)
        return rows, int(total_result.scalar_one())

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
