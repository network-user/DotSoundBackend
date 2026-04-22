from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WordTime(BaseModel):
    text: str = Field(max_length=200)
    start_ms: int = Field(ge=0)
    dur_ms: int = Field(ge=0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class SyncedLine(BaseModel):
    time_ms: int = Field(ge=0, description="Timestamp in milliseconds")
    text: str
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Alignment confidence 0.0–1.0",
    )
    word_times: list[WordTime] | None = None


class LyricsCreateRequest(BaseModel):
    plain_text: str = Field(max_length=10000)


class LyricsSyncRequest(BaseModel):
    synced_lines: list[SyncedLine] = Field(max_length=500)

    @field_validator("synced_lines")
    @classmethod
    def lines_sorted(cls, v: list[SyncedLine]) -> list[SyncedLine]:
        for i in range(1, len(v)):
            if v[i].time_ms < v[i - 1].time_ms:
                raise ValueError("synced_lines must be sorted by time_ms")
        return v


class LyricsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    track_id: int
    plain_text: str
    synced_lines: list[SyncedLine] | None = None
    source: str = "manual"
    source_name: str | None = Field(
        default=None,
        description=(
            "Human-readable provider label for user-facing "
            "attribution. Only populated when the underlying "
            "provider publishes a stable public name."
        ),
    )
    sync_source_name: str | None = Field(
        default=None,
        description=(
            "Provider that supplied the timecodes. May differ "
            "from source_name when sync is built locally "
            "(e.g. text from one provider, sync built "
            "audio-based)."
        ),
    )
    sync_quality: str | None = None
    sync_profile: str | None = None
    created_at: datetime
    updated_at: datetime


class LyricsAutoRequest(BaseModel):
    with_sync: bool = False
    bypass_cache: bool = Field(
        default=False,
        description=(
            "Skip the (artist,title) result cache for this run. "
            "Admin/debug only — gated at the route layer."
        ),
    )


class LyricsAutoResponse(BaseModel):
    task_id: str


class LyricsAutoStatusResponse(BaseModel):
    status: str
    stage: str | None = None
    percent: int | None = None
    logs: list[str] = []
