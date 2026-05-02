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
    total_plays: int = 0
    total_likes: int = 0
    total_followers: int = 0


class ArtistListenersResponse(BaseModel):
    artist_id: int
    current_month_listeners: int
    history: list[MonthlyListenersEntry]
