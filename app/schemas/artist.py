from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


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
    enriched_at: datetime | None = None
    created_at: datetime


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


class ArtistResolveResponse(BaseModel):
    id: int
