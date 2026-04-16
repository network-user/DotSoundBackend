from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SyncedLine(BaseModel):
    time_ms: int = Field(
        ge=0, description="Timestamp in milliseconds"
    )
    text: str
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Alignment confidence 0.0–1.0",
    )


class LyricsCreateRequest(BaseModel):
    plain_text: str = Field(max_length=10000)


class LyricsSyncRequest(BaseModel):
    synced_lines: list[SyncedLine] = Field(max_length=500)

    @field_validator("synced_lines")
    @classmethod
    def lines_sorted(
        cls, v: list[SyncedLine]
    ) -> list[SyncedLine]:
        for i in range(1, len(v)):
            if v[i].time_ms < v[i - 1].time_ms:
                raise ValueError(
                    "synced_lines must be sorted by time_ms"
                )
        return v


class LyricsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    track_id: int
    plain_text: str
    synced_lines: list[SyncedLine] | None = None
    source: str = "manual"
    created_at: datetime
    updated_at: datetime


class LyricsAutoRequest(BaseModel):
    with_sync: bool = False


class LyricsAutoResponse(BaseModel):
    task_id: str


class LyricsAutoStatusResponse(BaseModel):
    status: str
    stage: str | None = None
    logs: list[str] = []
