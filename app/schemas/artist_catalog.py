from datetime import date
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, computed_field

from app.schemas.track import TrackResponse


class ArtistCatalogReleaseSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    release_kind: str | None = None
    released_at: date | None = None
    display_position: int
    track_count: int
    cover_key: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cover_url(self) -> str | None:
        if not self.cover_key:
            return None
        return (
            f"/api/v1/tracks/cover_proxy?key="
            f"{quote(self.cover_key, safe='')}"
        )


class ArtistCatalogReleaseListResponse(BaseModel):
    items: list[ArtistCatalogReleaseSummaryResponse]
    total: int


class ArtistCatalogReleaseTrackRowResponse(BaseModel):
    position: int
    track: TrackResponse


class ArtistCatalogReleaseDetailResponse(BaseModel):
    id: int
    title: str
    release_kind: str | None = None
    released_at: date | None = None
    display_position: int
    cover_key: str | None = None
    tracks: list[ArtistCatalogReleaseTrackRowResponse]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cover_url(self) -> str | None:
        if not self.cover_key:
            return None
        return (
            f"/api/v1/tracks/cover_proxy?key="
            f"{quote(self.cover_key, safe='')}"
        )
