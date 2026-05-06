from pydantic import BaseModel


class ListenerStatsTopic(BaseModel):
    name: str
    minutes: int
    plays: int


class ListenerStatsResponse(BaseModel):
    period_days: int
    minutes_listened: int
    tracks_listened: int
    top_artists: list[ListenerStatsTopic]
    top_genres: list[ListenerStatsTopic]
