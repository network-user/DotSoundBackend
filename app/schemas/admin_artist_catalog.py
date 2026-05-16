from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.artist import ArtistResponse


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
    image_key: str | None = None
    soundcloud_user_id: int | None = None
    soundcloud_permalink: str | None = None
    catalog_sync_enabled: bool = True
    releases: list[AdminCatalogReleaseSummaryResponse]
    releases_total: int
    catalog_sync_state: Literal[
        "idle",
        "running",
        "success",
        "error",
    ] = "idle"
    catalog_sync_mode: Literal["full", "release"] | None = None
    catalog_sync_soundcloud_album_id: int | None = None
    catalog_sync_error: str | None = None
    catalog_sync_detail: dict[str, Any] | None = None
    catalog_sync_updated_at: str | None = None


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
    job_id: str | None = None


class AdminCatalogReleaseSyncQueuedResponse(
    AdminCatalogSyncQueuedResponse,
):
    soundcloud_album_id: int


class AdminCatalogBulkSyncRequest(BaseModel):
    artist_ids: list[int] = Field(..., min_length=1, max_length=200)


class AdminCatalogBulkSyncError(BaseModel):
    artist_id: int
    detail: str


class AdminCatalogBulkSyncResponse(BaseModel):
    queued: int
    job_ids: dict[int, str | None]
    errors: list[AdminCatalogBulkSyncError]


class AdminArtistLyricsSyncRequest(BaseModel):
    artist_ids: list[int] = Field(..., min_length=1, max_length=200)
    with_sync: bool = True
    include_existing_text: bool = True


class AdminArtistLyricsSyncResponse(BaseModel):
    queued: int
    job_ids: dict[int, str | None]
    errors: list[AdminCatalogBulkSyncError]


class AdminArtistBulkEnrichRequest(BaseModel):
    artist_ids: list[int] = Field(..., min_length=1, max_length=200)
    bypass_cache: bool = True


class AdminArtistBulkEnrichError(BaseModel):
    artist_id: int
    detail: str


class AdminArtistBulkEnrichResponse(BaseModel):
    queued: int
    job_ids: dict[int, str | None]
    errors: list[AdminArtistBulkEnrichError]


class AdminArtistListItemResponse(ArtistResponse):
    catalog_sync_state: Literal[
        "idle",
        "running",
        "success",
        "error",
    ] = "idle"
    catalog_sync_mode: str | None = None
    catalog_sync_updated_at: str | None = None


class AdminArtistListResponse(BaseModel):
    items: list[AdminArtistListItemResponse]
    total: int


class AdminArtistCatalogSyncEnabledRequest(BaseModel):
    enabled: bool


class AdminArtistCatalogSyncEnabledResponse(BaseModel):
    artist_id: int
    catalog_sync_enabled: bool


class AdminImportByScUrlRequest(BaseModel):
    url: str = Field(..., min_length=3, max_length=1024)


class AdminImportByScUrlResponse(BaseModel):
    artist_id: int
    artist_name: str
    created: bool
    catalog_sync_enabled: bool
    queued: bool
    job_id: str | None = None


class ArtistPipelineHealthResponse(BaseModel):
    enrichment_counts: dict[str, int]
    total: int
