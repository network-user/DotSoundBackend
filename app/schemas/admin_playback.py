from pydantic import BaseModel, Field


class AdminPlaybackVerifyResponse(BaseModel):
    ok: bool
    detail: str = ""
    http_status: int | None = None
    effective_track_id: int | None = None
    stream_protocol: str | None = None


class AdminPlaybackRepairEnqueueResponse(BaseModel):
    queued: bool
    track_id: int
    job_id: str | None = None
    progress_id: str | None = None
    detail: str = ""


class AdminPlaybackRepairBulkRequest(BaseModel):
    track_ids: list[int] = Field(..., min_length=1, max_length=5000)


class AdminPlaybackRepairBulkResponse(BaseModel):
    requested: int
    queued: int
    skipped: int
    missing: int
    job_ids: list[str] = Field(default_factory=list)
    progress_ids: list[str] = Field(default_factory=list)
    detail: str = ""


class AdminTelegramPlaybackNormalizeRequest(BaseModel):
    limit: int = Field(default=500, ge=1, le=5000)
    dry_run: bool = False


class AdminTelegramPlaybackNormalizeItem(BaseModel):
    track_id: int
    status: str
    title: str
    file_key: str
    tmp_key: str | None = None
    error: str | None = None


class AdminTelegramPlaybackNormalizeResponse(BaseModel):
    dry_run: bool
    found: int
    enqueued: int
    failed: int
    items: list[AdminTelegramPlaybackNormalizeItem] = Field(
        default_factory=list
    )
    detail: str = ""


class AdminSoundCloudPlaybackAuditRequest(BaseModel):
    search: str | None = Field(default=None, max_length=128)
    limit: int = Field(default=500, ge=1, le=5000)
    include_recently_checked: bool = False


class AdminSoundCloudEncryptedUnsupportedCleanupRequest(BaseModel):
    limit: int = Field(default=500, ge=1, le=5000)
    dry_run: bool = False


class AdminSoundCloudEncryptedUnsupportedCleanupResponse(BaseModel):
    matched: int
    updated: int
    dry_run: bool
    track_ids: list[int] = Field(default_factory=list)
    detail: str = ""
