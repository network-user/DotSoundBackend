from datetime import datetime

from pydantic import BaseModel, Field


class PlaylistInviteOut(BaseModel):
    token: str
    expires_at: datetime


class PlaylistInviteAccept(BaseModel):
    token: str = Field(min_length=8, max_length=200)
