import pytest
from pydantic import ValidationError

from app.schemas.album import (
    AlbumCreateRequest,
    AlbumResponse,
    AlbumUpdateRequest,
    AlbumWithTracksResponse,
)


def test_album_create_valid() -> None:
    req = AlbumCreateRequest(title="My Album")
    assert req.title == "My Album"
    assert req.description is None
    assert req.is_public is True


def test_album_create_full() -> None:
    req = AlbumCreateRequest(
        title="Album",
        description="Desc",
        is_public=False,
    )
    assert req.description == "Desc"
    assert req.is_public is False


def test_album_create_missing_title() -> None:
    with pytest.raises(ValidationError):
        AlbumCreateRequest()


def test_album_create_title_too_long() -> None:
    with pytest.raises(ValidationError):
        AlbumCreateRequest(title="x" * 256)


def test_album_create_title_max_length() -> None:
    req = AlbumCreateRequest(title="x" * 255)
    assert len(req.title) == 255


def test_album_create_description_too_long() -> None:
    with pytest.raises(ValidationError):
        AlbumCreateRequest(
            title="A", description="x" * 2001
        )


def test_album_create_description_max_length() -> None:
    req = AlbumCreateRequest(
        title="A", description="x" * 2000
    )
    assert len(req.description) == 2000


def test_album_update_all_none() -> None:
    req = AlbumUpdateRequest()
    assert req.title is None
    assert req.description is None
    assert req.is_public is None


def test_album_update_partial() -> None:
    req = AlbumUpdateRequest(title="New Title")
    assert req.title == "New Title"
    assert req.is_public is None


def test_album_update_title_too_long() -> None:
    with pytest.raises(ValidationError):
        AlbumUpdateRequest(title="x" * 256)


def test_album_update_description_too_long() -> None:
    with pytest.raises(ValidationError):
        AlbumUpdateRequest(description="x" * 2001)


def test_album_response_valid() -> None:
    resp = AlbumResponse(
        id=1,
        title="A",
        owner_id=2,
        is_public=True,
        created_at="2024-01-01T00:00:00",
    )
    assert resp.id == 1
    assert resp.cover_key is None
    assert resp.description is None


def test_album_response_missing_required() -> None:
    with pytest.raises(ValidationError):
        AlbumResponse(id=1, title="A")


def test_album_with_tracks_empty() -> None:
    resp = AlbumWithTracksResponse(
        id=1,
        title="A",
        owner_id=2,
        is_public=True,
        created_at="2024-01-01T00:00:00",
    )
    assert resp.tracks == []


def test_album_response_wrong_type_id() -> None:
    with pytest.raises(ValidationError):
        AlbumResponse(
            id="abc",
            title="A",
            owner_id=2,
            is_public=True,
            created_at="2024-01-01T00:00:00",
        )
