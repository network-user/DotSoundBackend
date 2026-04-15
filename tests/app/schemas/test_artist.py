from datetime import datetime

from app.schemas.artist import (
    ArtistDetailResponse,
    ArtistListResponse,
    ArtistResponse,
)


def test_artist_response() -> None:
    resp = ArtistResponse(
        id=1,
        name="Drake",
        image_key=None,
        source="internal",
        bio=None,
        created_at=datetime(2024, 1, 1),
    )
    assert resp.name == "Drake"
    assert resp.source == "internal"


def test_artist_detail_response() -> None:
    resp = ArtistDetailResponse(
        id=1,
        name="Drake",
        image_key=None,
        source="soundcloud",
        bio="Canadian rapper",
        created_at=datetime(2024, 1, 1),
        track_count=42,
    )
    assert resp.track_count == 42


def test_artist_list_response() -> None:
    resp = ArtistListResponse(items=[], total=0)
    assert resp.total == 0
    assert resp.items == []
