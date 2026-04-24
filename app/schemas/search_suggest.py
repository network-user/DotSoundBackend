from __future__ import annotations

from pydantic import BaseModel, Field


class SuggestItemResponse(BaseModel):
    kind: str = Field(
        description='Either "track" or "artist"',
    )
    id: int
    title: str | None = None
    name: str | None = None
    model_config = {
        "json_schema_extra": {
            "example": {
                "kind": "track",
                "id": 1,
                "title": "My Song",
                "name": "The Artist",
            }
        }
    }


class SuggestListResponse(BaseModel):
    items: list[SuggestItemResponse] = []
    model_config = {
        "json_schema_extra": {
            "example": {
                "items": [
                    {
                        "kind": "track",
                        "id": 1,
                        "title": "Hit",
                        "name": "DJ",
                    }
                ]
            }
        }
    }
