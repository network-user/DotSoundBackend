import pytest
from pydantic import ValidationError

from app.schemas.follow import (
    FollowerResponse,
    FollowListResponse,
    FollowToggleResponse,
)


def test_follow_toggle_valid() -> None:
    resp = FollowToggleResponse(
        user_id=1, following=True
    )
    assert resp.user_id == 1
    assert resp.following is True


def test_follow_toggle_unfollow() -> None:
    resp = FollowToggleResponse(
        user_id=1, following=False
    )
    assert resp.following is False


def test_follow_toggle_missing_field() -> None:
    with pytest.raises(ValidationError):
        FollowToggleResponse(user_id=1)


def test_follow_toggle_wrong_type() -> None:
    with pytest.raises(ValidationError):
        FollowToggleResponse(
            user_id="abc", following=True
        )


def test_follower_response_valid() -> None:
    resp = FollowerResponse(id=5)
    assert resp.id == 5
    assert resp.username is None
    assert resp.display_name is None
    assert resp.avatar_key is None


def test_follower_response_full() -> None:
    resp = FollowerResponse(
        id=5,
        username="alice",
        display_name="Alice",
        avatar_key="avatars/alice.jpg",
    )
    assert resp.username == "alice"
    assert resp.display_name == "Alice"


def test_follower_response_missing_id() -> None:
    with pytest.raises(ValidationError):
        FollowerResponse()


def test_follow_list_valid() -> None:
    resp = FollowListResponse(
        items=[
            FollowerResponse(id=1),
            FollowerResponse(id=2),
        ],
        total=2,
    )
    assert len(resp.items) == 2
    assert resp.total == 2


def test_follow_list_empty() -> None:
    resp = FollowListResponse(items=[], total=0)
    assert resp.items == []
    assert resp.total == 0


def test_follow_list_missing_total() -> None:
    with pytest.raises(ValidationError):
        FollowListResponse(items=[])
