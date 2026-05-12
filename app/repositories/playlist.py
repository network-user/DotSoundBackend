import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.playlist import Playlist, PlaylistTrack
from app.models.track import Track
from app.repositories.track import TrackRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class PlaylistRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _exclude_hidden_sources():  # noqa: ANN205
        hidden = ("youtube",)
        source_platform = func.lower(func.coalesce(Track.source_platform, ""))
        imported_from = func.lower(func.coalesce(Track.imported_from, ""))
        return (~source_platform.in_(hidden)) & (~imported_from.in_(hidden))

    async def get_by_id(self, playlist_id: int) -> Playlist | None:
        return await self._session.get(Playlist, playlist_id)

    async def list_by_owner(
        self,
        owner_id: int,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Playlist], int]:
        total = (
            await self._session.execute(
                select(func.count()).where(Playlist.owner_id == owner_id)
            )
        ).scalar_one()

        result = await self._session.execute(
            select(Playlist)
            .where(Playlist.owner_id == owner_id)
            .order_by(Playlist.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def create(
        self,
        name: str,
        owner_id: int,
        is_public: bool,
        playlist_type: str = "user",
        is_featured: bool = False,
        source_url: str | None = None,
        cover_key: str | None = None,
        description: str | None = None,
    ) -> Playlist:
        playlist = Playlist(
            name=name,
            owner_id=owner_id,
            is_public=is_public,
            playlist_type=playlist_type,
            is_featured=is_featured,
            source_url=source_url,
            cover_key=cover_key,
            description=description,
        )
        self._session.add(playlist)
        await self._session.flush()
        await self._session.refresh(playlist)
        logger.debug(
            "db_playlist_created",
            playlist_id=playlist.id,
            owner_id=owner_id,
            playlist_type=playlist_type,
        )
        return playlist

    async def update(
        self,
        playlist: Playlist,
        name: str | None = None,
        is_public: bool | None = None,
        owner_id: int | None = None,
        is_featured: bool | None = None,
        cover_key: str | None = None,
        description: str | None = None,
    ) -> Playlist:
        if name is not None:
            playlist.name = name
        if is_public is not None:
            playlist.is_public = is_public
        if owner_id is not None:
            playlist.owner_id = owner_id
        if is_featured is not None:
            playlist.is_featured = is_featured
        if cover_key is not None:
            playlist.cover_key = cover_key
        if description is not None:
            playlist.description = description
        await self._session.flush()
        return playlist

    async def list_featured(self, limit: int = 20) -> list[Playlist]:
        result = await self._session.execute(
            select(Playlist)
            .where(
                Playlist.is_featured.is_(True),
                Playlist.is_public.is_(True),
            )
            .order_by(Playlist.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_visible_tracks(self, playlist_id: int) -> int:
        q = (
            select(func.count(Track.id))
            .select_from(PlaylistTrack)
            .join(Track, PlaylistTrack.track_id == Track.id)
            .where(
                PlaylistTrack.playlist_id == playlist_id,
                Track.is_active.is_(True),
                self._exclude_hidden_sources(),
                TrackRepository._playback_listing_allowed(),
            )
        )
        out = await self._session.execute(q)
        row = out.scalar_one()
        return int(row)

    async def delete(self, playlist: Playlist) -> None:
        await self._session.delete(playlist)
        await self._session.flush()
        logger.debug("db_playlist_deleted", playlist_id=playlist.id)

    async def add_track(
        self,
        playlist_id: int,
        track_id: int,
        position: int = 0,
    ) -> PlaylistTrack:
        result = await self._session.execute(
            select(PlaylistTrack).where(
                PlaylistTrack.playlist_id == playlist_id,
                PlaylistTrack.track_id == track_id,
            )
        )
        found = result.scalar_one_or_none()
        if found:
            logger.debug(
                "db_playlist_track_already_exists",
                playlist_id=playlist_id,
                track_id=track_id,
            )
            return found

        pt = PlaylistTrack(
            playlist_id=playlist_id,
            track_id=track_id,
            position=position,
        )
        self._session.add(pt)
        await self._session.flush()
        logger.debug(
            "db_playlist_track_added",
            playlist_id=playlist_id,
            track_id=track_id,
        )
        return pt

    async def remove_track(self, playlist_id: int, track_id: int) -> bool:
        result = await self._session.execute(
            delete(PlaylistTrack).where(
                PlaylistTrack.playlist_id == playlist_id,
                PlaylistTrack.track_id == track_id,
            )
        )
        removed = result.rowcount > 0
        if removed:
            await self._session.flush()
            await self.compact_track_positions(playlist_id)
        return removed

    async def compact_track_positions(self, playlist_id: int) -> None:
        result = await self._session.execute(
            select(PlaylistTrack)
            .where(PlaylistTrack.playlist_id == playlist_id)
            .order_by(
                PlaylistTrack.position.asc(),
                PlaylistTrack.track_id.asc(),
            )
        )
        rows = list(result.scalars().all())
        for pos, pt in enumerate(rows):
            if pt.position != pos:
                pt.position = pos
        await self._session.flush()

    async def add_track_at_end(
        self,
        playlist_id: int,
        track_id: int,
    ) -> bool:
        result = await self._session.execute(
            select(PlaylistTrack).where(
                PlaylistTrack.playlist_id == playlist_id,
                PlaylistTrack.track_id == track_id,
            )
        )
        if result.scalar_one_or_none():
            return False
        max_pos = await self._session.execute(
            select(
                func.coalesce(func.max(PlaylistTrack.position), -1),
            ).where(PlaylistTrack.playlist_id == playlist_id)
        )
        nxt = int(max_pos.scalar_one()) + 1
        pt = PlaylistTrack(
            playlist_id=playlist_id,
            track_id=track_id,
            position=nxt,
        )
        self._session.add(pt)
        await self._session.flush()
        logger.debug(
            "db_playlist_track_appended",
            playlist_id=playlist_id,
            track_id=track_id,
            position=nxt,
        )
        return True

    async def set_track_order(
        self,
        playlist_id: int,
        ordered_track_ids: list[int],
    ) -> None:
        result = await self._session.execute(
            select(PlaylistTrack).where(
                PlaylistTrack.playlist_id == playlist_id,
            )
        )
        rows = {pt.track_id: pt for pt in result.scalars().all()}
        if set(ordered_track_ids) != set(rows.keys()):
            raise ValueError(
                "track_ids must list every playlist track exactly once",
            )
        for pos, tid in enumerate(ordered_track_ids):
            rows[tid].position = pos
        await self._session.flush()

    async def search_public(
        self,
        query: str,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Playlist], int]:
        pattern = f"%{query}%"
        cond = (
            Playlist.is_public.is_(True)
            & Playlist.name.ilike(pattern)
        )
        total_r = await self._session.execute(
            select(func.count(Playlist.id)).where(cond)
        )
        total = int(total_r.scalar_one())
        result = await self._session.execute(
            select(Playlist)
            .where(cond)
            .order_by(Playlist.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def list_for_admin(
        self,
        *,
        page: int,
        size: int,
        search: str | None,
    ) -> tuple[list[tuple[Playlist, int]], int]:
        tc = (
            select(func.count(PlaylistTrack.track_id))
            .where(PlaylistTrack.playlist_id == Playlist.id)
            .scalar_subquery()
        )
        base = select(Playlist, tc)
        count_q = select(func.count(Playlist.id))
        if search:
            pattern = f"%{search}%"
            cond = Playlist.name.ilike(pattern)
            base = base.where(cond)
            count_q = count_q.where(cond)
        total_r = await self._session.execute(count_q)
        total = int(total_r.scalar_one())
        base = (
            base.order_by(Playlist.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        result = await self._session.execute(base)
        return list(result.all()), total

    async def get_tracks(self, playlist_id: int) -> list[Track]:
        result = await self._session.execute(
            select(Track)
            .join(
                PlaylistTrack,
                PlaylistTrack.track_id == Track.id,
            )
            .where(
                PlaylistTrack.playlist_id == playlist_id,
                Track.is_active.is_(True),
                self._exclude_hidden_sources(),
                TrackRepository._playback_listing_allowed(),
            )
            .order_by(PlaylistTrack.position)
        )
        return list(result.scalars().all())

    async def get_tracks_bulk(
        self, playlist_ids: list[int]
    ) -> dict[int, list[Track]]:
        """Batch counterpart to :meth:`get_tracks` for N playlists."""
        if not playlist_ids:
            return {}
        result = await self._session.execute(
            select(PlaylistTrack.playlist_id, Track)
            .join(
                PlaylistTrack,
                PlaylistTrack.track_id == Track.id,
            )
            .where(
                PlaylistTrack.playlist_id.in_(playlist_ids),
                Track.is_active.is_(True),
                self._exclude_hidden_sources(),
                TrackRepository._playback_listing_allowed(),
            )
            .order_by(
                PlaylistTrack.playlist_id,
                PlaylistTrack.position,
            )
        )
        out: dict[int, list[Track]] = {pid: [] for pid in playlist_ids}
        for pid, track in result.all():
            out[pid].append(track)
        return out
