
import pytest
from pydantic import ValidationError

from app.schemas.user import (
    AvatarResponse,
    TrackStatsItem,
    UserCreate,
    UserResponse,
    UserStatsResponse,
    UserUpdateRequest,
)


def test_user_create_minimal() -> None:
    req = UserCreate(first_name="Alice")
    assert req.first_name == "Alice"
    assert req.telegram_id is None
    assert req.email is None
    assert req.username is None
    assert req.last_name is None
    assert req.auth_provider == "telegram"


def test_user_create_full() -> None:
    req = UserCreate(
        telegram_id=123456,
        email="alice@example.com",
        username="alice",
        first_name="Alice",
        last_name="Smith",
        auth_provider="email",
    )
    assert req.telegram_id == 123456
    assert req.email == "alice@example.com"


def test_user_create_missing_first_name() -> None:
    with pytest.raises(ValidationError):
        UserCreate()


def test_user_response_valid() -> None:
    resp = UserResponse(
        id=1,
        first_name="Alice",
        is_active=True,
        created_at="2024-01-01T00:00:00",
    )
    assert resp.id == 1
    assert resp.telegram_id is None
    assert resp.email_verified is False
    assert resp.auth_provider == "telegram"
    assert resp.totp_enabled is False
    assert resp.is_admin is False


def test_user_response_missing_required() -> None:
    with pytest.raises(ValidationError):
        UserResponse(id=1)


def test_user_update_valid() -> None:
    req = UserUpdateRequest(display_name="Bob")
    assert req.display_name == "Bob"


def test_user_update_empty() -> None:
    req = UserUpdateRequest()
    assert req.display_name is None


def test_user_update_display_name_too_long() -> None:
    with pytest.raises(ValidationError):
        UserUpdateRequest(
            display_name="x" * 65
        )


def test_user_update_display_name_max() -> None:
    req = UserUpdateRequest(
        display_name="x" * 64
    )
    assert len(req.display_name) == 64


def test_user_update_display_name_single_char() -> None:
    req = UserUpdateRequest(display_name="A")
    assert req.display_name == "A"


def test_user_update_leading_space() -> None:
    with pytest.raises(ValidationError):
        UserUpdateRequest(display_name=" Bob")


def test_user_update_trailing_space() -> None:
    with pytest.raises(ValidationError):
        UserUpdateRequest(display_name="Bob ")


def test_user_update_both_spaces() -> None:
    with pytest.raises(ValidationError):
        UserUpdateRequest(display_name=" Bob ")


def test_user_update_inner_spaces_ok() -> None:
    req = UserUpdateRequest(
        display_name="Bob Smith"
    )
    assert req.display_name == "Bob Smith"


def test_avatar_response_valid() -> None:
    resp = AvatarResponse(
        avatar_url="https://cdn.example.com/a.jpg"
    )
    assert "cdn.example.com" in resp.avatar_url


def test_avatar_response_missing() -> None:
    with pytest.raises(ValidationError):
        AvatarResponse()


def test_track_stats_item_valid() -> None:
    item = TrackStatsItem(
        id=1,
        title="Song",
        artist="Art",
        play_count=100,
    )
    assert item.play_count == 100
    assert item.cover_key is None


def test_track_stats_item_missing() -> None:
    with pytest.raises(ValidationError):
        TrackStatsItem(id=1, title="S")


def test_user_stats_response_valid() -> None:
    resp = UserStatsResponse(
        user_id=1,
        total_tracks=5,
        total_plays=100,
        top_tracks=[
            TrackStatsItem(
                id=1,
                title="S",
                artist=None,
                play_count=50,
            )
        ],
    )
    assert resp.total_tracks == 5
    assert resp.total_likes == 0
    assert resp.followers_count == 0
    assert resp.following_count == 0


def test_user_stats_negative_tracks() -> None:
    with pytest.raises(ValidationError):
        UserStatsResponse(
            user_id=1,
            total_tracks=-1,
            total_plays=0,
            top_tracks=[],
        )


def test_user_stats_negative_plays() -> None:
    with pytest.raises(ValidationError):
        UserStatsResponse(
            user_id=1,
            total_tracks=0,
            total_plays=-1,
            top_tracks=[],
        )


def test_user_stats_missing_top_tracks() -> None:
    with pytest.raises(ValidationError):
        UserStatsResponse(
            user_id=1,
            total_tracks=0,
            total_plays=0,
        )
