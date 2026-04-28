from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.artist import ArtistRepository
from app.repositories.artist_catalog import ArtistCatalogRepository
from app.schemas.artist_catalog import (
    ArtistCatalogReleaseDetailResponse,
    ArtistCatalogReleaseListResponse,
    ArtistCatalogReleaseSummaryResponse,
    ArtistCatalogReleaseTrackRowResponse,
)
from app.schemas.track import TrackResponse


class ArtistCatalogReadService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._artists = ArtistRepository(session)
        self._catalog = ArtistCatalogRepository(session)

    async def list_releases(
        self,
        artist_id: int,
    ) -> ArtistCatalogReleaseListResponse | None:
        if not await self._artists.get_by_id(artist_id):
            return None
        rows = await self._catalog.list_releases_with_track_counts(artist_id)
        items = [
            ArtistCatalogReleaseSummaryResponse(
                id=rel.id,
                title=rel.title,
                release_kind=rel.release_kind,
                released_at=rel.released_at,
                display_position=rel.display_position,
                track_count=n,
                cover_key=rel.cover_key,
            )
            for rel, n in rows
        ]
        return ArtistCatalogReleaseListResponse(
            items=items,
            total=len(items),
        )

    async def get_release_detail(
        self,
        artist_id: int,
        release_id: int,
    ) -> ArtistCatalogReleaseDetailResponse | None:
        if not await self._artists.get_by_id(artist_id):
            return None
        packed = await self._catalog.get_release_with_tracks_for_artist(
            artist_id,
            release_id,
        )
        if packed is None:
            return None
        rel, ordered = packed
        track_rows = [
            ArtistCatalogReleaseTrackRowResponse(
                position=pos,
                track=TrackResponse.model_validate(tr),
            )
            for pos, tr in ordered
        ]
        return ArtistCatalogReleaseDetailResponse(
            id=rel.id,
            title=rel.title,
            release_kind=rel.release_kind,
            released_at=rel.released_at,
            display_position=rel.display_position,
            cover_key=rel.cover_key,
            tracks=track_rows,
        )
