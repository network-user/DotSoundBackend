from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class DiscographyItemResponse(BaseModel):
    title: str
    year: int | None = None
    type: str | None = None
    url: str | None = None


class ArtistSourceProfileResponse(BaseModel):
    source_id: str
    source_name: str
    source_page_url: str | None = None
    bio: str | None = None
    birth_date: date | None = None
    birthplace: str | None = None
    country: str | None = None
    image_url: str | None = None
    website_url: str | None = None
    discography: list[DiscographyItemResponse] | None = None


class ArtistResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    image_key: str | None = None
    image_url: str | None = None
    source: str = "internal"
    bio: str | None = None
    birth_date: date | None = None
    birthplace: str | None = None
    country: str | None = None
    website_url: str | None = None
    enrichment_status: str = "pending"
    enrichment_confidence: float | None = None
    enriched_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None
    monthly_listeners: int = 0


class ArtistListResponse(BaseModel):
    items: list[ArtistResponse]
    total: int


class ArtistDetailResponse(ArtistResponse):
    track_count: int = 0
    age: int | None = None
    discography: list[dict] | None = None
    source_profiles: (
        list[ArtistSourceProfileResponse] | None
    ) = None
    primary_source_id: str | None = None
    follower_count: int = 0


class ArtistResolveResponse(BaseModel):
    id: int


class ArtistShareCardResponse(BaseModel):
    artist_id: int
    display_name: str
    image_url: str | None = None
    profile_url: str
    deep_link: str | None = None
    total_tracks: int = Field(ge=0, default=0)
    followers_count: int = Field(ge=0, default=0)
    monthly_listeners: int = Field(ge=0, default=0)
    top_track_titles: list[str] = Field(default_factory=list)
