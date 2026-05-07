from pydantic import BaseModel

from app.schemas.artist import ArtistResponse
from app.schemas.track import TrackResponse


class HomeHighlightResponse(BaseModel):
    track: TrackResponse
    label: str
    reason: str | None = None
    hero_image_key: str | None = None


class HomeSectionResponse(BaseModel):
    title: str
    section_type: str
    tracks: list[TrackResponse]


class HomePageResponse(BaseModel):
    sections: list[HomeSectionResponse]
    highlights: list[HomeHighlightResponse]
    maturity: str = "cold"


class SimilarTracksResponse(BaseModel):
    seed_track_id: int
    tracks: list[TrackResponse]


class DailyMixResponse(BaseModel):
    tracks: list[TrackResponse]
    generated_at: str


class RadioQueueResponse(BaseModel):
    seed_type: str
    seed_id: str
    tracks: list[TrackResponse]


class DailyPlaylistResponse(BaseModel):
    internal_tracks: list[TrackResponse]
    external_tracks: list[TrackResponse]
    global_top: list[TrackResponse]
    generated_at: str
    expires_at: str


class WeeklyPlaylistResponse(BaseModel):
    internal_tracks: list[TrackResponse]
    external_tracks: list[TrackResponse]
    generated_at: str
    expires_at: str


class UserChoicePlaylistResponse(BaseModel):
    tracks: list[TrackResponse]
    generated_at: str
    score_version: str


class WeeklyTopPlaylistResponse(BaseModel):
    tracks: list[TrackResponse]
    generated_at: str
    expires_at: str
    score_version: str
    window_days: int


class ForgottenTreasuresPlaylistResponse(BaseModel):
    tracks: list[TrackResponse]
    generated_at: str
    expires_at: str
    score_version: str
    min_like_age_days: int
    silence_days: int


class GenreMixItemResponse(BaseModel):
    genre: str
    title: str
    tracks: list[TrackResponse]


class GenreMixesResponse(BaseModel):
    mixes: list[GenreMixItemResponse]


class GenreMixOverrideRequest(BaseModel):
    title: str
    track_ids: list[int]


class DiscoverGenreCard(BaseModel):
    genre: str
    title: str
    cover_key: str | None = None
    track_count: int = 0


class DiscoverResponse(BaseModel):
    trending_tracks: list[TrackResponse]
    suggested_artists: list[ArtistResponse]
    genre_cards: list[DiscoverGenreCard]
    recent_genres: list[str]
