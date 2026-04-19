from datetime import datetime

from app.schemas.artist import (
    ArtistDetailResponse,
    ArtistListResponse,
    ArtistResponse,
    ArtistSourceProfileResponse,
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


def test_artist_detail_with_source_profiles() -> None:
    resp = ArtistDetailResponse(
        id=1,
        name="Drake",
        image_key=None,
        source="internal",
        bio="merged bio",
        created_at=datetime(2024, 1, 1),
        track_count=10,
        primary_source_id="wiki_en",
        source_profiles=[
            ArtistSourceProfileResponse(
                source_id="wiki_en",
                source_name="Wikipedia (EN)",
                source_page_url=(
                    "https://en.wikipedia.org/wiki/Drake"
                ),
                bio="wiki bio",
                discography=[
                    {
                        "title": "Take Care",
                        "year": 2011,
                    }
                ],
            )
        ],
    )
    assert resp.primary_source_id == "wiki_en"
    assert resp.source_profiles is not None
    assert len(resp.source_profiles) == 1
    assert resp.source_profiles[0].source_name == (
        "Wikipedia (EN)"
    )
    assert resp.source_profiles[0].discography is not None


def test_artist_detail_optional_source_profiles() -> None:
    resp = ArtistDetailResponse(
        id=1,
        name="Drake",
        image_key=None,
        source="internal",
        created_at=datetime(2024, 1, 1),
    )
    assert resp.source_profiles is None
    assert resp.primary_source_id is None
