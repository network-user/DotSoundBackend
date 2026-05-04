from pydantic import BaseModel, ConfigDict


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


class FollowedArtistItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    image_key: str | None = None
    source: str = "internal"
    bio: str | None = None
    track_count: int = 0


class FollowedArtistListResponse(BaseModel):
    items: list[FollowedArtistItem]
    total: int
