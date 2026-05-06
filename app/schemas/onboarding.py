from pydantic import BaseModel, ConfigDict, Field


class OnboardingPreferencesRequest(BaseModel):
    genres: list[str] = Field(default_factory=list)
    artist_ids: list[int] = Field(
        default_factory=list
    )
    moods: list[str] = Field(default_factory=list)


class CalibrationItem(BaseModel):
    track_id: int
    liked: bool


class CalibrationRequest(BaseModel):
    items: list[CalibrationItem] = Field(
        min_length=1, max_length=10
    )


class OnboardingStatusResponse(BaseModel):
    onboarding_completed: bool
    calibration_completed: bool
    preferred_genres: list[str] | None = None
    preferred_moods: list[str] | None = None
    import_prompt_acknowledged: bool = False
    can_import_from_telegram: bool = False
    has_telegram_profile_music: bool | None = None


class ArtistBriefResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    image_key: str | None = None


class SmartSkipResponse(BaseModel):
    applied_genres: list[str] = Field(
        default_factory=list
    )
    applied_artist_ids: list[int] = Field(
        default_factory=list
    )
    applied_moods: list[str] = Field(
        default_factory=list
    )


ActivationEventMeta = dict[
    str, str | int | float | bool | None
]


class ActivationEventRequest(BaseModel):
    event: str = Field(min_length=1, max_length=64)
    meta: ActivationEventMeta | None = None
