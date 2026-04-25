from pydantic import BaseModel, ConfigDict, Field


class AuthorTrackStatsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    track_id: int
    play_count: int
    like_count: int
    listen_events_7d: int = Field(
        description="Listen signal rows in last 7d",
    )
    listen_events_30d: int
    play_count_display: int
    like_count_display: int
