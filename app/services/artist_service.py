import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artist import Artist
from app.repositories.artist import ArtistRepository
from dotsound_private_core.services.artist_normalizer import (
    is_fuzzy_match,
    normalize_name,
    resolve_artist_names,
)

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
        matches = resolve_artist_names(raw_artist_string)
        if not matches:
            return []

        linked: list[Artist] = []
        for i, m in enumerate(matches):
            artist = await self._find_or_create(
                canonical=m.raw,
                normalized=m.canonical,
                source=source,
                external_id=(
                    external_id if i == 0 else None
                ),
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
        existing = (
            await self._repo.find_by_normalized_name(
                normalized
            )
        )
        if existing:
            return existing

        all_artists = await self._repo.search(
            normalized[:3], limit=50
        )
        for candidate in all_artists:
            if is_fuzzy_match(
                normalized, candidate.name_normalized
            ):
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
        return artist

    async def get_by_id(
        self, artist_id: int
    ) -> Artist | None:
        return await self._repo.get_by_id(artist_id)

    async def search(
        self,
        query: str,
        limit: int = 20,
    ) -> list[Artist]:
        normalized = normalize_name(query)
        return await self._repo.search(
            normalized, limit
        )

    async def list_popular(
        self,
        limit: int = 50,
        genre_filter: list[str] | None = None,
    ) -> list[Artist]:
        return await self._repo.list_popular(
            limit, genre_filter
        )

    async def get_track_artists(
        self, track_id: int
    ) -> list[Artist]:
        return await self._repo.get_track_artists(
            track_id
        )
