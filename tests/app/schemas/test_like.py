from datetime import datetime

import pytest
from pydantic import ValidationError

from app.schemas.like import (
    DislikeResponse,
    DislikeToggleResponse,
    LikeResponse,
    LikeToggleResponse,
)


def test_like_toggle_response_valid() -> None:
    resp = LikeToggleResponse(
        track_id=1, liked=True
    )
    assert resp.track_id == 1
    assert resp.liked is True


def test_like_toggle_response_unlike() -> None:
    resp = LikeToggleResponse(
        track_id=1, liked=False
    )
    assert resp.liked is False


def test_like_toggle_response_missing_field() -> None:
    with pytest.raises(ValidationError):
        LikeToggleResponse(track_id=1)


def test_like_toggle_response_wrong_type() -> None:
    with pytest.raises(ValidationError):
        LikeToggleResponse(
            track_id="abc", liked=True
        )


def test_like_response_valid() -> None:
    now = datetime(2024, 1, 1)
    resp = LikeResponse(
        user_id=1,
        track_id=2,
        created_at=now,
    )
    assert resp.user_id == 1
    assert resp.track_id == 2
    assert resp.created_at == now


def test_like_response_missing_field() -> None:
    with pytest.raises(ValidationError):
        LikeResponse(user_id=1, track_id=2)


def test_like_response_wrong_type() -> None:
    with pytest.raises(ValidationError):
        LikeResponse(
            user_id="x",
            track_id=2,
            created_at="2024-01-01T00:00:00",
        )


def test_dislike_toggle_response_valid() -> None:
    resp = DislikeToggleResponse(
        track_id=10, disliked=True
    )
    assert resp.track_id == 10
    assert resp.disliked is True


def test_dislike_toggle_missing_field() -> None:
    with pytest.raises(ValidationError):
        DislikeToggleResponse(track_id=1)


def test_dislike_response_valid() -> None:
    now = datetime(2024, 6, 15)
    resp = DislikeResponse(
        user_id=3,
        track_id=4,
        created_at=now,
    )
    assert resp.user_id == 3
    assert resp.track_id == 4


def test_dislike_response_missing_field() -> None:
    with pytest.raises(ValidationError):
        DislikeResponse(user_id=1, track_id=2)
