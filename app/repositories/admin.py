"""Repository for admin-only DB queries.

This file replaces the inline ``select(...)`` calls that used to
live inside ``app/api/v1/admin/{tracks,users,complaints}.py``,
closing the tech debt item in AGENTS.md.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import and_, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import Subquery

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

    def _latest_playback_failure_details(self) -> Subquery:
        return (
            select(
                TrackPlaybackFailureEvent.track_id.label("track_id"),
                TrackPlaybackFailureEvent.detail_truncated.label(
                    "detail_truncated"
                ),
                func.row_number()
                .over(
                    partition_by=TrackPlaybackFailureEvent.track_id,
                    order_by=(
                        TrackPlaybackFailureEvent.created_at.desc(),
                        TrackPlaybackFailureEvent.id.desc(),
                    ),
                )
                .label("rn"),
            )
            .subquery()
        )

    def _apply_playback_error_filter(
        self,
        query: Select[Any],
        *,
        playback_error: str | None,
    ) -> Select[Any]:
        if not playback_error:
            return query
        latest = self._latest_playback_failure_details()
        return (
            query.join(
                latest,
                and_(latest.c.track_id == Track.id, latest.c.rn == 1),
            )
            .where(latest.c.detail_truncated.ilike(f"%{playback_error}%"))
        )

    def _soundcloud_track_filter(self) -> ColumnElement[bool]:
        source = func.lower(func.coalesce(Track.source, ""))
        source_platform = func.lower(func.coalesce(Track.source_platform, ""))
        imported_from = func.lower(func.coalesce(Track.imported_from, ""))
        return or_(
            source == "soundcloud",
            source_platform == "soundcloud",
            imported_from == "soundcloud",
            Track.sc_url.isnot(None),
        )

    def _soundcloud_encrypted_unsupported_filter(
        self,
        *,
        deleted_reason: str,
    ) -> ColumnElement[bool]:
        return or_(
            and_(
                self._soundcloud_track_filter(),
                Track.access_mode == "official_embed",
            ),
            Track.deleted_reason == deleted_reason,
        )

    def _apply_simple_track_search(
        self,
        query: Select[Any],
        *,
        search: str | None,
    ) -> Select[Any]:
        if not search:
            return query
        pattern = f"%{search}%"
        return query.where(
            Track.title.ilike(pattern) | Track.artist.ilike(pattern)
        )

    def _synced_lines_present(self) -> ColumnElement[bool]:
        return and_(
            TrackLyrics.synced_lines.isnot(None),
            func.json_array_length(TrackLyrics.synced_lines) > 0,
        )

    def _apply_track_list_filters(
        self,
        query: Select[Any],
        *,
        is_active: bool | None,
        without_lyrics: bool,
        lyrics_catalog_miss_only: bool,
        lyrics_sync_status: str | None,
        search: str | None,
        for_playlist_owner_id: int | None,
        playable_only: bool,
    ) -> Select[Any]:
        if without_lyrics or lyrics_sync_status:
            query = query.outerjoin(
                TrackLyrics, TrackLyrics.track_id == Track.id
            )
        if lyrics_catalog_miss_only:
            query = query.where(
                Track.lyrics_catalog_miss_at.isnot(None),
            )
        elif without_lyrics:
            query = query.where(TrackLyrics.id.is_(None))
        if lyrics_sync_status == "synced":
            query = query.where(
                TrackLyrics.id.isnot(None),
                self._synced_lines_present(),
            )
        elif lyrics_sync_status == "unsynced":
            query = query.where(
                TrackLyrics.id.isnot(None),
                ~self._synced_lines_present(),
            )
        elif lyrics_sync_status == "missing":
            query = query.where(TrackLyrics.id.is_(None))
        if is_active is not None:
            query = query.where(Track.is_active.is_(is_active))
        if for_playlist_owner_id is not None:
            tr = TrackRepository
            pub: ColumnElement[bool] = (
                Track.is_active.is_(True)
                & Track.is_public.is_(True)
                & tr._exclude_hidden_sources()
                & tr._playback_listing_allowed()
            )
            own: ColumnElement[bool] = (
                Track.is_active.is_(True)
                & (Track.uploaded_by_id == for_playlist_owner_id)
                & (Track.catalog_type == "ugc")
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

    def _apply_sort(
        self,
        query: Select[Any],
        *,
        sort_by: str | None,
    ) -> Select[Any]:
        if sort_by == "visibility_asc":
            return query.order_by(
                Track.is_active.asc(),
                Track.created_at.desc(),
            )
        if sort_by == "visibility_desc":
            return query.order_by(
                Track.is_active.desc(),
                Track.created_at.desc(),
            )
        return query.order_by(Track.created_at.desc())

    async def list_tracks(
        self,
        *,
        page: int = 1,
        size: int = 20,
        is_active: bool | None = None,
        without_lyrics: bool = False,
        lyrics_catalog_miss_only: bool = False,
        lyrics_sync_status: str | None = None,
        search: str | None = None,
        for_playlist_owner_id: int | None = None,
        playable_only: bool = False,
        sort_by: str | None = None,
    ) -> tuple[list[Track], int]:
        query = self._apply_track_list_filters(
            select(Track),
            is_active=is_active,
            without_lyrics=without_lyrics,
            lyrics_catalog_miss_only=lyrics_catalog_miss_only,
            lyrics_sync_status=lyrics_sync_status,
            search=search,
            for_playlist_owner_id=for_playlist_owner_id,
            playable_only=playable_only,
        )
        count_query = self._apply_track_list_filters(
            select(func.count(Track.id)),
            is_active=is_active,
            without_lyrics=without_lyrics,
            lyrics_catalog_miss_only=lyrics_catalog_miss_only,
            lyrics_sync_status=lyrics_sync_status,
            search=search,
            for_playlist_owner_id=for_playlist_owner_id,
            playable_only=playable_only,
        )
        query = (
            self._apply_sort(query, sort_by=sort_by)
            .offset((page - 1) * size)
            .limit(size)
        )
        result = await self._session.execute(query)
        rows = list(result.scalars().all())
        total_result = await self._session.execute(count_query)
        return rows, int(total_result.scalar_one())

    async def get_visibility_counts(
        self,
        *,
        search: str | None = None,
    ) -> tuple[int, int]:
        base = select(Track.is_active, func.count(Track.id).label("c"))
        if search:
            pattern = f"%{search}%"
            base = base.where(
                Track.title.ilike(pattern) | Track.artist.ilike(pattern)
            )
        base = base.where(
            Track.deleted_at.is_(None),
        ).group_by(Track.is_active)
        result = await self._session.execute(base)
        hidden = 0
        visible = 0
        for row in result.all():
            if row[0]:
                visible = int(row[1])
            else:
                hidden = int(row[1])
        return hidden, visible

    async def list_track_ids(
        self,
        *,
        is_active: bool | None = None,
        without_lyrics: bool = False,
        lyrics_catalog_miss_only: bool = False,
        lyrics_sync_status: str | None = None,
        search: str | None = None,
        for_playlist_owner_id: int | None = None,
        playable_only: bool = False,
    ) -> tuple[list[int], int]:
        query = self._apply_track_list_filters(
            select(Track.id),
            is_active=is_active,
            without_lyrics=without_lyrics,
            lyrics_catalog_miss_only=lyrics_catalog_miss_only,
            lyrics_sync_status=lyrics_sync_status,
            search=search,
            for_playlist_owner_id=for_playlist_owner_id,
            playable_only=playable_only,
        ).order_by(Track.created_at.desc())
        count_query = self._apply_track_list_filters(
            select(func.count(Track.id)),
            is_active=is_active,
            without_lyrics=without_lyrics,
            lyrics_catalog_miss_only=lyrics_catalog_miss_only,
            lyrics_sync_status=lyrics_sync_status,
            search=search,
            for_playlist_owner_id=for_playlist_owner_id,
            playable_only=playable_only,
        )
        rows = await self._session.execute(query)
        total = await self._session.execute(count_query)
        return [int(track_id) for track_id in rows.scalars().all()], int(
            total.scalar_one()
        )

    async def track_lyrics_sync_statuses(
        self,
        track_ids: list[int],
    ) -> dict[int, dict[str, object]]:
        if not track_ids:
            return {}
        result = await self._session.execute(
            select(
                TrackLyrics.track_id,
                TrackLyrics.synced_lines,
            ).where(TrackLyrics.track_id.in_(track_ids))
        )
        by_track = {
            int(track_id): synced_lines
            for track_id, synced_lines in result.all()
        }
        statuses: dict[int, dict[str, object]] = {}
        for track_id in track_ids:
            if track_id not in by_track:
                statuses[track_id] = {
                    "has_synced_timecodes": False,
                    "lyrics_sync_status": "missing",
                }
                continue
            synced = by_track[track_id]
            has_sync = isinstance(synced, list) and len(synced) > 0
            statuses[track_id] = {
                "has_synced_timecodes": has_sync,
                "lyrics_sync_status": "synced" if has_sync else "unsynced",
            }
        return statuses

    async def list_tracks_playback_unavailable(
        self,
        *,
        page: int = 1,
        size: int = 20,
        search: str | None = None,
        playback_error: str | None = None,
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
        q = self._apply_playback_error_filter(
            q,
            playback_error=playback_error,
        )
        cq = self._apply_playback_error_filter(
            cq,
            playback_error=playback_error,
        )
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
        playback_error: str | None = None,
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
        q = self._apply_playback_error_filter(
            q,
            playback_error=playback_error,
        )
        cq = self._apply_playback_error_filter(
            cq,
            playback_error=playback_error,
        )
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

    async def list_tracks_soundcloud_encrypted_unsupported(
        self,
        *,
        page: int = 1,
        size: int = 20,
        search: str | None = None,
        deleted_reason: str,
    ) -> tuple[list[Track], int]:
        cond = self._soundcloud_encrypted_unsupported_filter(
            deleted_reason=deleted_reason,
        )
        q = self._apply_simple_track_search(
            select(Track).where(cond),
            search=search,
        )
        cq = self._apply_simple_track_search(
            select(func.count(Track.id)).where(cond),
            search=search,
        )
        q = (
            q.order_by(desc(Track.playback_last_failure_at), desc(Track.id))
            .offset((page - 1) * size)
            .limit(size)
        )
        result = await self._session.execute(q)
        rows = list(result.scalars().all())
        total_result = await self._session.execute(cq)
        return rows, int(total_result.scalar_one())

    async def list_track_ids_soundcloud_encrypted_unsupported(
        self,
        *,
        search: str | None = None,
        deleted_reason: str,
    ) -> tuple[list[int], int]:
        cond = self._soundcloud_encrypted_unsupported_filter(
            deleted_reason=deleted_reason,
        )
        q = self._apply_simple_track_search(
            select(Track.id).where(cond),
            search=search,
        ).order_by(desc(Track.playback_last_failure_at), desc(Track.id))
        cq = self._apply_simple_track_search(
            select(func.count(Track.id)).where(cond),
            search=search,
        )
        rows = await self._session.execute(q)
        total_result = await self._session.execute(cq)
        return [int(track_id) for track_id in rows.scalars().all()], int(
            total_result.scalar_one()
        )

    async def list_soundcloud_official_embed_cleanup_candidate_ids(
        self,
        *,
        limit: int,
    ) -> tuple[list[int], int]:
        cond = and_(
            self._soundcloud_track_filter(),
            Track.access_mode == "official_embed",
            Track.deleted_at.is_(None),
        )
        total_result = await self._session.execute(
            select(func.count(Track.id)).where(cond),
        )
        rows = await self._session.execute(
            select(Track.id)
            .where(cond)
            .order_by(desc(Track.id))
            .limit(limit),
        )
        return [int(track_id) for track_id in rows.scalars().all()], int(
            total_result.scalar_one()
        )

    async def mark_soundcloud_encrypted_unsupported_cleanup(
        self,
        *,
        track_ids: list[int],
        deleted_reason: str,
        failure_at: datetime,
    ) -> int:
        if not track_ids:
            return 0
        result = await self._session.execute(
            update(Track)
            .where(Track.id.in_(track_ids))
            .values(
                access_mode="third_party_stream",
                is_active=False,
                is_public=False,
                deleted_reason=deleted_reason,
                playback_last_failure_at=failure_at,
                playback_last_http_status=422,
                playback_last_failure_source="admin_sc_encrypted_cleanup",
                playback_recovery_failed_at=failure_at,
                playback_last_checked_at=failure_at,
            )
        )
        rowcount = getattr(result, "rowcount", 0)
        return int(rowcount or 0)

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
        condition: ColumnElement[bool] = User.deleted_at.is_not(None)
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
