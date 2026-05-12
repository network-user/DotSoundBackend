from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PlaylistInviteOut(BaseModel):
    token: str
    expires_at: datetime


class PlaylistInviteAccept(BaseModel):
    token: str = Field(min_length=8, max_length=200)


class PlaylistCollaboratorItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    role: str
    username: str | None
    display_name: str | None
    created_at: datetime
