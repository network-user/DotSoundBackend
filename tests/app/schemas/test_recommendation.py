from app.schemas.recommendation import (
    DailyMixResponse,
    HomePageResponse,
    HomeSectionResponse,
    RadioQueueResponse,
    SimilarTracksResponse,
)


def test_home_section() -> None:
    section = HomeSectionResponse(
        title="For You",
        section_type="personalized",
        tracks=[],
    )
    assert section.title == "For You"
    assert section.tracks == []


def test_home_page() -> None:
    resp = HomePageResponse(
        sections=[], maturity="cold"
    )
    assert resp.maturity == "cold"
    assert resp.sections == []


def test_similar_tracks() -> None:
    resp = SimilarTracksResponse(
        seed_track_id=1, tracks=[]
    )
    assert resp.seed_track_id == 1


def test_daily_mix() -> None:
    resp = DailyMixResponse(
        tracks=[],
        generated_at="2024-01-01T00:00:00",
    )
    assert resp.generated_at is not None


def test_radio_queue() -> None:
    resp = RadioQueueResponse(
        seed_type="track",
        seed_id="42",
        tracks=[],
    )
    assert resp.seed_type == "track"
    assert resp.seed_id == "42"
