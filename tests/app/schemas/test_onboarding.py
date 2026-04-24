import pytest
from pydantic import ValidationError

from app.schemas.onboarding import (
    ArtistBriefResponse,
    CalibrationItem,
    CalibrationRequest,
    OnboardingPreferencesRequest,
    OnboardingStatusResponse,
)


def test_preferences_defaults() -> None:
    req = OnboardingPreferencesRequest()
    assert req.genres == []
    assert req.artist_ids == []
    assert req.moods == []


def test_preferences_with_data() -> None:
    req = OnboardingPreferencesRequest(
        genres=["rock", "pop"],
        artist_ids=[1, 2],
        moods=["chill"],
    )
    assert len(req.genres) == 2
    assert len(req.artist_ids) == 2


def test_calibration_item() -> None:
    item = CalibrationItem(
        track_id=1, liked=True
    )
    assert item.track_id == 1
    assert item.liked is True


def test_calibration_request_valid() -> None:
    req = CalibrationRequest(
        items=[
            CalibrationItem(
                track_id=1, liked=True
            ),
            CalibrationItem(
                track_id=2, liked=False
            ),
        ]
    )
    assert len(req.items) == 2


def test_calibration_request_empty() -> None:
    with pytest.raises(ValidationError):
        CalibrationRequest(items=[])


def test_calibration_request_too_many() -> None:
    with pytest.raises(ValidationError):
        CalibrationRequest(
            items=[
                CalibrationItem(
                    track_id=i, liked=True
                )
                for i in range(11)
            ]
        )


def test_onboarding_status() -> None:
    resp = OnboardingStatusResponse(
        onboarding_completed=True,
        calibration_completed=False,
        preferred_genres=["rock"],
        preferred_moods=None,
        import_prompt_acknowledged=True,
        can_import_from_telegram=False,
        has_telegram_profile_music=None,
    )
    assert resp.onboarding_completed is True
    assert resp.calibration_completed is False
    assert resp.import_prompt_acknowledged is True


def test_artist_brief() -> None:
    resp = ArtistBriefResponse(
        id=1,
        name="Drake",
        image_key=None,
    )
    assert resp.name == "Drake"
