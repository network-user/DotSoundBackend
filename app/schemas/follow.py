from pydantic import BaseModel, ConfigDict


class FollowToggleResponse(BaseModel):
    user_id: int
    following: bool


class FollowerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str | None = None
    display_name: str | None = None
    avatar_key: str | None = None


class FollowListResponse(BaseModel):
    items: list[FollowerResponse]
    total: int
