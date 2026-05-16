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


class AdminSoundCloudPlaybackAuditRequest(BaseModel):
    search: str | None = Field(default=None, max_length=128)
    limit: int = Field(default=500, ge=1, le=5000)
    include_recently_checked: bool = False
