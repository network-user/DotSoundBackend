from pydantic import BaseModel, ConfigDict, Field


class OnboardingCompleteRequest(BaseModel):
    """Implicit acceptance recorded when user taps the final
    "Готово/Начать" button. Mini App must send the legal pack
    version it displayed below the button so the server stores
    exactly what the user saw.
    """

    legal_accepted_version: str = Field(
        min_length=1, max_length=32
    )


class OnboardingPreferencesRequest(BaseModel):
    genres: list[str] = Field(default_factory=list)
    artist_ids: list[int] = Field(default_factory=list)
    moods: list[str] = Field(default_factory=list)


class CalibrationItem(BaseModel):
    track_id: int
    liked: bool | None


class CalibrationRequest(BaseModel):
    items: list[CalibrationItem] = Field(min_length=1, max_length=10)


class OnboardingStatusResponse(BaseModel):
    onboarding_completed: bool
    calibration_completed: bool
    preferred_genres: list[str] | None = None
    preferred_moods: list[str] | None = None
    import_prompt_acknowledged: bool = False
    can_import_from_telegram: bool = False
    has_telegram_profile_music: bool | None = None
    profile_completed: bool = False
    legal_accepted_version: str | None = None
    is_adult_confirmed: bool = False


class ArtistBriefResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    image_key: str | None = None


class SmartSkipResponse(BaseModel):
    applied_genres: list[str] = Field(default_factory=list)
    applied_artist_ids: list[int] = Field(default_factory=list)
    applied_moods: list[str] = Field(default_factory=list)
    enabled: bool = True


ActivationEventMeta = dict[str, str | int | float | bool | None]


class ActivationEventRequest(BaseModel):
    event: str = Field(min_length=1, max_length=64)
    meta: ActivationEventMeta | None = None


class ProfileDefaultsResponse(BaseModel):
    suggested_display_name: str
    current_display_name: str | None = None
    suggested_avatar_url: str | None = None
    has_custom_avatar: bool = False
    auth_provider: str = "telegram"
    suggested_initials: str = ""
    locale: str | None = None


class OnboardingProfileSubmitRequest(BaseModel):
    display_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
    )
    use_default_avatar: bool = False
    locale: str | None = Field(
        default=None,
        min_length=2,
        max_length=10,
    )


class OnboardingProfileSubmitResponse(BaseModel):
    display_name: str
    avatar_url: str | None = None
    profile_completed: bool


class TasteSwipeDecision(BaseModel):
    track_id: int
    decision: str = Field(
        pattern=r"^(like|dislike|skip)$",
    )


class TasteSwipeBatchRequest(BaseModel):
    decisions: list[TasteSwipeDecision] = Field(
        default_factory=list,
        max_length=20,
    )


class TasteSwipeBatchResponse(BaseModel):
    saved: int
    swipe_total: int


class GenreBubbleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    genre: str
    track_count: int = 0
    sample_cover_keys: list[str] = Field(
        default_factory=list,
    )


class OnboardingBootstrapResponse(BaseModel):
    """Single round-trip payload for the onboarding wizard.

    Bundles status + profile defaults + the locale-curated
    bubble list so the client can render the first frame
    without two extra requests.
    """

    status: OnboardingStatusResponse
    profile_defaults: ProfileDefaultsResponse
    genre_bubbles: list[GenreBubbleResponse] = Field(
        default_factory=list,
    )
    show_import_offer: bool = False
