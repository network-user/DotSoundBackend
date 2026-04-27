from pydantic import BaseModel

from app.schemas.track import TrackResponse


class HomeSectionResponse(BaseModel):
    title: str
    section_type: str
    tracks: list[TrackResponse]


class HomePageResponse(BaseModel):
    sections: list[HomeSectionResponse]
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
