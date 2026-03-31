from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SyncedLine(BaseModel):
    time_ms: int = Field(ge=0, description="Timestamp in milliseconds")
    text: str


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
    created_at: datetime
    updated_at: datetime
