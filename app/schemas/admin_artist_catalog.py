from datetime import date

from pydantic import BaseModel, Field


class AdminCatalogReleaseSummaryResponse(BaseModel):
    id: int
    title: str
    release_kind: str | None = None
    released_at: date | None = None
    display_position: int
    track_count: int
    cover_key: str | None = None
    manual_lock: bool
    soundcloud_album_id: int | None = None


class AdminArtistCatalogOverviewResponse(BaseModel):
    artist_id: int
    soundcloud_user_id: int | None = None
    soundcloud_permalink: str | None = None
    releases: list[AdminCatalogReleaseSummaryResponse]
    releases_total: int


class AdminArtistSoundcloudPatch(BaseModel):
    soundcloud_user_id: int | None = None
    soundcloud_permalink: str | None = Field(None, max_length=256)


class AdminCatalogReleaseCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    release_kind: str | None = Field(None, max_length=32)
    released_at: date | None = None
    soundcloud_album_id: int | None = None
    manual_lock: bool = True


class AdminCatalogReleasePatch(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=512)
    release_kind: str | None = Field(None, max_length=32)
    released_at: date | None = None
    display_position: int | None = Field(None, ge=0)
    manual_lock: bool | None = None


class AdminCatalogReleaseOrderBody(BaseModel):
    ordered_release_ids: list[int] = Field(default_factory=list)


class AdminCatalogReleaseTracksBody(BaseModel):
    track_ids: list[int] = Field(default_factory=list)


class AdminCatalogSyncQueuedResponse(BaseModel):
    queued: bool = True
    task: str


class AdminCatalogReleaseSyncQueuedResponse(
    AdminCatalogSyncQueuedResponse,
):
    soundcloud_album_id: int
