from pydantic import BaseModel


class ArtistFollowToggleResponse(BaseModel):
    artist_id: int
    following: bool
    follower_count: int


class ArtistFollowStatusResponse(BaseModel):
    artist_id: int
    following: bool


class MonthlyListenersEntry(BaseModel):
    year: int
    month: int
    unique_listeners: int


class ArtistListenersResponse(BaseModel):
    artist_id: int
    current_month_listeners: int
    history: list[MonthlyListenersEntry]
