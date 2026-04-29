from __future__ import annotations

from pydantic import BaseModel, Field


class PlatformAuthorSearchItem(BaseModel):
    id: int
    display_name: str = Field(
        description="Primary label: display_name or first + last name",
    )
    username: str | None = None
    avatar_url: str


class PlatformAuthorSearchListResponse(BaseModel):
    items: list[PlatformAuthorSearchItem] = Field(default_factory=list)
