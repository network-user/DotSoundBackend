
import pytest
from pydantic import ValidationError

from app.schemas.playlist import (
    PlaylistAddTrack,
    PlaylistCreate,
    PlaylistResponse,
    PlaylistUpdate,
    PlaylistWithTracksResponse,
)


def test_playlist_create_valid() -> None:
    req = PlaylistCreate(name="My Playlist")
    assert req.name == "My Playlist"
    assert req.is_public is True


def test_playlist_create_private() -> None:
    req = PlaylistCreate(
        name="Secret", is_public=False
    )
    assert req.is_public is False


def test_playlist_create_missing_name() -> None:
    with pytest.raises(ValidationError):
        PlaylistCreate()


def test_playlist_create_name_too_long() -> None:
    with pytest.raises(ValidationError):
        PlaylistCreate(name="x" * 257)


def test_playlist_create_name_max_length() -> None:
    req = PlaylistCreate(name="x" * 256)
    assert len(req.name) == 256


def test_playlist_update_all_none() -> None:
    req = PlaylistUpdate()
    assert req.name is None
    assert req.is_public is None


def test_playlist_update_partial() -> None:
    req = PlaylistUpdate(name="Renamed")
    assert req.name == "Renamed"


def test_playlist_update_name_too_long() -> None:
    with pytest.raises(ValidationError):
        PlaylistUpdate(name="x" * 257)


def test_playlist_response_valid() -> None:
    resp = PlaylistResponse(
        id=1,
        name="P",
        owner_id=2,
        is_public=True,
        created_at="2024-01-01T00:00:00",
    )
    assert resp.id == 1
    assert resp.name == "P"


def test_playlist_response_missing_field() -> None:
    with pytest.raises(ValidationError):
        PlaylistResponse(id=1, name="P")


def test_playlist_with_tracks_empty() -> None:
    resp = PlaylistWithTracksResponse(
        id=1,
        name="P",
        owner_id=2,
        is_public=True,
        created_at="2024-01-01T00:00:00",
    )
    assert resp.tracks == []


def test_playlist_add_track_valid() -> None:
    req = PlaylistAddTrack(track_id=5)
    assert req.track_id == 5
    assert req.position == 0


def test_playlist_add_track_with_position() -> None:
    req = PlaylistAddTrack(
        track_id=5, position=3
    )
    assert req.position == 3


def test_playlist_add_track_negative_pos() -> None:
    with pytest.raises(ValidationError):
        PlaylistAddTrack(track_id=5, position=-1)


def test_playlist_add_track_missing_id() -> None:
    with pytest.raises(ValidationError):
        PlaylistAddTrack()


def test_playlist_add_track_zero_pos() -> None:
    req = PlaylistAddTrack(
        track_id=1, position=0
    )
    assert req.position == 0
