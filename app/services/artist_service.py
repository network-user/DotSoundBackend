import structlog
from dotsound_private_core.services.artist_normalizer import (
    is_fuzzy_match,
    normalize_name,
    resolve_artist_names,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artist import Artist, TrackArtist
from app.models.track import Track
from app.repositories.artist import ArtistRepository
from app.repositories.track import TrackRepository

logger = structlog.get_logger(__name__)


class ArtistService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = ArtistRepository(session)
        self._session = session

    async def resolve_and_link(
        self,
        track_id: int,
        raw_artist_string: str,
        source: str = "internal",
        external_id: str | None = None,
    ) -> list[Artist]:
        raw_matches = resolve_artist_names(raw_artist_string)
        if not raw_matches:
            return []
        seen_c: set[str] = set()
        matches = []
        for m in raw_matches:
            if m.canonical in seen_c:
                continue
            seen_c.add(m.canonical)
            matches.append(m)
        if not matches:
            return []

        linked: list[Artist] = []
        for i, m in enumerate(matches):
            artist = await self._find_or_create(
                canonical=m.raw,
                normalized=m.canonical,
                source=source,
                external_id=(external_id if i == 0 else None),
            )
            await self._repo.link_track(
                track_id=track_id,
                artist_id=artist.id,
                role=m.role,
                position=i,
            )
            linked.append(artist)
        return linked

    async def _find_or_create(
        self,
        canonical: str,
        normalized: str,
        source: str,
        external_id: str | None,
    ) -> Artist:
        existing = await self._repo.find_by_normalized_name(normalized)
        if existing:
            return existing

        all_artists = await self._repo.search(normalized[:3], limit=50)
        for candidate in all_artists:
            if is_fuzzy_match(normalized, candidate.name_normalized):
                logger.info(
                    "artist_fuzzy_matched",
                    query=normalized,
                    matched=candidate.name,
                )
                return candidate

        artist = await self._repo.create(
            name=canonical,
            name_normalized=normalized,
            source=source,
            external_id=external_id,
        )
        logger.info(
            "artist_created",
            name=canonical,
            id=artist.id,
        )
        try:
            from app.services.search_index_notify import (
                schedule_reindex_artist,
            )

            await schedule_reindex_artist(artist.id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "artist_es_schedule_failed",
                artist_id=artist.id,
                error=str(exc),
            )
        try:
            from app.services.artist_enrichment_worker import (
                enrich_artist_task,
            )

            await enrich_artist_task.kiq(artist_id=artist.id)
        except Exception:
            logger.exception(
                "artist_enrich_schedule_failed",
                artist_id=artist.id,
            )
        return artist

    async def get_by_id(self, artist_id: int) -> Artist | None:
        return await self._repo.get_by_id(artist_id)

    async def find_or_create_by_name(self, raw_name: str) -> Artist | None:
        """Look up artist by (fuzzy) name, creating a new row if missing.

        Returns None if the raw name cannot be normalized into anything
        usable. Newly-created rows schedule background enrichment and get
        back-linked to any existing tracks whose `track.artist` string
        matches.
        """
        matches = resolve_artist_names(raw_name)
        if not matches:
            return None
        primary = matches[0]
        artist = await self._find_or_create(
            canonical=primary.raw,
            normalized=primary.canonical,
            source="internal",
            external_id=None,
        )
        await self._backfill_track_links(artist)
        return artist

    async def _backfill_track_links(self, artist: Artist) -> None:
        """Link tracks whose string `artist` field matches
        to this Artist row.
        """
        existing = await self._session.execute(
            select(TrackArtist.track_id).where(
                TrackArtist.artist_id == artist.id
            )
        )
        already_linked = {row[0] for row in existing.all()}

        result = await self._session.execute(
            select(Track.id, Track.artist).where(Track.artist.is_not(None))
        )
        candidates = []
        for track_id, raw_artist in result.all():
            if track_id in already_linked:
                continue
            if not raw_artist:
                continue
            if is_fuzzy_match(
                artist.name_normalized,
                normalize_name(raw_artist),
            ) or artist.name_normalized in normalize_name(raw_artist):
                candidates.append(track_id)

        for track_id in candidates:
            await self._repo.link_track(
                track_id=track_id,
                artist_id=artist.id,
                role="primary",
                position=0,
            )
        if candidates:
            logger.info(
                "artist_tracks_backfilled",
                artist_id=artist.id,
                count=len(candidates),
            )

    async def search(
        self,
        query: str,
        limit: int = 20,
    ) -> list[Artist]:
        from app.config import settings
        from app.search.es_client import es_available
        from app.services import search_query_service

        if (
            settings.elasticsearch_enabled
            and (settings.elasticsearch_url or "").strip()
            and es_available()
        ):
            ids = await search_query_service.es_search_artists(
                query, limit=limit
            )
            if ids is not None and ids:
                return await self._repo.get_by_ids_preserve_order(ids[:limit])
        normalized = normalize_name(query)
        return await self._repo.search(normalized, limit)

    async def list_popular(
        self,
        limit: int = 50,
        genre_filter: list[str] | None = None,
    ) -> list[Artist]:
        return await self._repo.list_popular(limit, genre_filter)

    async def get_track_artists(self, track_id: int) -> list[Artist]:
        return await self._repo.get_track_artists(track_id)

    async def list_artist_tracks(
        self,
        artist_id: int,
        page: int = 1,
        size: int = 20,
        public_only: bool = True,
        max_artist_tracks: int = 500,
    ) -> tuple[list[Track], int]:
        track_ids = await self._repo.get_artist_track_ids(
            artist_id, limit=max_artist_tracks
        )
        if not track_ids:
            return [], 0
        track_repo = TrackRepository(self._session)
        offset = (page - 1) * size
        return await track_repo.list_by_artist_track_ids(
            track_ids=track_ids,
            offset=offset,
            limit=size,
            public_only=public_only,
        )
