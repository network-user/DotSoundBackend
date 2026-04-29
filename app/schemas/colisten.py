from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CoListenRoomState(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    host_id: int
    dj_id: int | None = None
    track_id: int
    position_ms: int
    is_playing: bool
    epoch: int
    expires_at: datetime


class CoListenCreateBody(BaseModel):
    track_id: int = Field(..., ge=1)


class CoListenPatchBody(BaseModel):
    position_ms: int | None = None
    is_playing: bool | None = None
    track_id: int | None = None
