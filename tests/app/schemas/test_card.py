from datetime import datetime

import pytest
from pydantic import ValidationError

from app.schemas.card import (
    TrackAlbumInfo,
    TrackAuthorInfo,
    TrackCardResponse,
)


def test_track_author_info_valid() -> None:
    info = TrackAuthorInfo(id=1)
    assert info.id == 1
    assert info.display_name is None
    assert info.username is None
    assert info.avatar_key is None


def test_track_author_info_full() -> None:
    info = TrackAuthorInfo(
        id=1,
        display_name="Alice",
        username="alice",
        avatar_key="avatars/1.jpg",
    )
    assert info.display_name == "Alice"


def test_track_author_info_missing_id() -> None:
    with pytest.raises(ValidationError):
        TrackAuthorInfo()


def test_track_album_info_valid() -> None:
    info = TrackAlbumInfo(id=1, title="Album")
    assert info.id == 1
    assert info.title == "Album"
    assert info.cover_key is None


def test_track_album_info_missing() -> None:
    with pytest.raises(ValidationError):
        TrackAlbumInfo(id=1)


def test_track_card_response_minimal() -> None:
    resp = TrackCardResponse(
        id=1,
        title="Song",
        play_count=0,
        created_at="2024-01-01T00:00:00",
    )
    assert resp.id == 1
    assert resp.artist is None
    assert resp.genre is None
    assert resp.duration_seconds is None
    assert resp.cover_url is None
    assert resp.author is None
    assert resp.album is None
    assert resp.has_lyrics is False


def test_track_card_response_full() -> None:
    author = TrackAuthorInfo(
        id=5, display_name="DJ"
    )
    album = TrackAlbumInfo(
        id=10, title="Best Of"
    )
    resp = TrackCardResponse(
        id=1,
        title="Song",
        artist="DJ",
        genre="electronic",
        duration_seconds=240,
        play_count=999,
        cover_url="/covers/1.jpg",
        created_at="2024-06-15T12:00:00",
        author=author,
        album=album,
        has_lyrics=True,
    )
    assert resp.author.display_name == "DJ"
    assert resp.album.title == "Best Of"
    assert resp.has_lyrics is True


def test_track_card_response_missing_required() -> None:
    with pytest.raises(ValidationError):
        TrackCardResponse(id=1, title="S")


def test_track_card_response_wrong_type() -> None:
    with pytest.raises(ValidationError):
        TrackCardResponse(
            id="abc",
            title="S",
            play_count=0,
            created_at="2024-01-01T00:00:00",
        )
