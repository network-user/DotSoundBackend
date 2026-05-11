import structlog
from dotsound_private_core.services.artist_normalizer import (
    is_fuzzy_match,
    normalize_name,
    resolve_artist_names,
)
from dotsound_private_core.services.similarity_signal_policy import (
    rank_similar_artists_for_display,
)
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artist import Artist, TrackArtist
from app.models.track import Track
from app.repositories.artist import ArtistRepository
from app.repositories.artist_catalog import ArtistCatalogRepository
from app.repositories.track import TrackRepository
from app.repositories.user import UserRepository

logger = structlog.get_logger(__name__)


class ArtistService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = ArtistRepository(session)
        self._session = session
        self._user_repo = UserRepository(session)

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

    async def ensure_owned_artist_for_user(
        self,
        *,
        user_id: int,
        preferred_name: str,
    ) -> Artist:
        canonical = preferred_name.strip()
        normalized = normalize_name(canonical)
        if not normalized:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Artist name is invalid",
            )
        user_conflict = await self._user_repo.find_by_display_name_normalized(
            normalized
        )
        if user_conflict and user_conflict.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Artist name conflicts with another user",
            )
        owned = await self._repo.find_by_owner_user_id(user_id)
        by_name = await self._repo.find_by_normalized_name(normalized)
        if by_name and by_name.owner_user_id not in (None, user_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Artist name is already taken",
            )
        if owned:
            if by_name and by_name.id != owned.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Artist name is already taken",
                )
            if owned.name != canonical or owned.name_normalized != normalized:
                owned.name = canonical
                owned.name_normalized = normalized
                await self._session.flush()
            return owned
        if by_name and by_name.owner_user_id is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Artist name is already taken",
            )
        artist = await self._repo.create(
            name=canonical,
            name_normalized=normalized,
            source="internal",
            owner_user_id=user_id,
        )
        return artist

    async def get_by_id(self, artist_id: int) -> Artist | None:
        return await self._repo.get_by_id(artist_id)

    async def get_owned_for_user(
        self, user_id: int
    ) -> Artist | None:
        return await self._repo.find_by_owner_user_id(user_id)

    async def update_owned_profile(
        self,
        *,
        user_id: int,
        bio: str | None | object = ...,
        country: str | None | object = ...,
        birth_date: object = ...,
        birthplace: str | None | object = ...,
        website_url: str | None | object = ...,
        image_key: str | None | object = ...,
    ) -> Artist:
        """Patch artist-only fields on the owned artist row.

        Each kwarg accepts ``...`` (unset, leave as-is) or an
        explicit value (including ``None`` for clear). The ``name``
        is intentionally NOT editable here -- it follows
        ``user.display_name`` via ``user_service.update_profile``.
        """
        owned = await self._repo.find_by_owner_user_id(user_id)
        if owned is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "Artist profile not created yet. "
                    "Call POST /artists/me/ensure first."
                ),
            )
        changed = False
        if bio is not ...:
            owned.bio = bio if not bio else str(bio).strip() or None
            changed = True
        if country is not ...:
            owned.country = (
                str(country).strip().upper()[:2] if country else None
            )
            changed = True
        if birth_date is not ...:
            owned.birth_date = birth_date  # type: ignore[assignment]
            changed = True
        if birthplace is not ...:
            owned.birthplace = (
                str(birthplace).strip()[:128] if birthplace else None
            )
            changed = True
        if website_url is not ...:
            owned.website_url = (
                str(website_url).strip()[:512] if website_url else None
            )
            changed = True
        if image_key is not ...:
            owned.image_key = image_key  # type: ignore[assignment]
            changed = True
        if changed:
            await self._session.flush()
        return owned

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

    async def link_title_artists(
        self,
        track_id: int,
        title: str,
        existing_artist_count: int = 0,
    ) -> None:
        from app.services.title_normalizer import parse_title
        parsed = parse_title(title)
        if parsed.is_empty():
            return
        pos = existing_artist_count
        for name in parsed.all_names():
            normalized = normalize_name(name)
            if not normalized:
                continue
            try:
                artist = await self._find_or_create(
                    canonical=name,
                    normalized=normalized,
                    source="internal",
                    external_id=None,
                )
                await self._repo.link_track(
                    track_id=track_id,
                    artist_id=artist.id,
                    role="featured",
                    position=pos,
                )
                pos += 1
            except Exception:
                logger.warning(
                    "title_artist_link_failed",
                    track_id=track_id,
                    artist_name=name,
                )

    async def list_artist_tracks(
        self,
        artist_id: int,
        page: int = 1,
        size: int = 20,
        public_only: bool = True,
        max_artist_tracks: int = 500,
    ) -> tuple[list[Track], int]:
        track_ids = await self._repo.get_all_artist_track_ids(
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

    async def list_similar_artists_for_discovery(
        self,
        artist_id: int,
        *,
        limit: int = 10,
    ) -> list[Artist]:
        seed = await self._repo.get_by_id(artist_id)
        if seed is None:
            return []

        catalog_repo = ArtistCatalogRepository(self._session)
        station = await catalog_repo.get_coartist_overlap_counts(
            [artist_id],
            scope="station",
        )
        album = await catalog_repo.get_coartist_overlap_counts(
            [artist_id],
            scope="album",
        )
        ml_pairs = (
            await self._repo.list_similar_artists_from_similarity_index(
                artist_id,
                limit=max(limit * 4, 24),
            )
        )
        ml_scores = {i: s for i, s in ml_pairs}
        ranked_ids = rank_similar_artists_for_display(
            station,
            album,
            ml_scores,
            limit=max(limit * 4, 24),
        )
        trimmed = [
            rid for rid in ranked_ids if rid != artist_id
        ][:limit]
        if not trimmed:
            popular = await self._repo.list_popular(
                limit=max(limit * 3, 30),
            )
            trimmed = [
                a.id for a in popular if a.id != artist_id
            ][:limit]
        return await self._repo.get_by_ids_preserve_order(trimmed)
