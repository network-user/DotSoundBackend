import pytest
from pydantic import ValidationError

from app.schemas.signal import (
    ListenEventRequest,
    SearchClickRequest,
)


def test_listen_event_valid() -> None:
    req = ListenEventRequest(
        track_id=1,
        duration_listened=120,
        total_duration=200,
        source_context="home",
    )
    assert req.track_id == 1
    assert req.duration_listened == 120


def test_listen_event_minimal() -> None:
    req = ListenEventRequest(
        track_id=1,
        duration_listened=0,
    )
    assert req.total_duration is None
    assert req.source_context is None


def test_listen_event_negative_duration() -> None:
    with pytest.raises(ValidationError):
        ListenEventRequest(
            track_id=1,
            duration_listened=-1,
        )


def test_search_click_valid() -> None:
    req = SearchClickRequest(
        query="drake",
        results_count=10,
        clicked_track_id=5,
    )
    assert req.query == "drake"


def test_search_click_minimal() -> None:
    req = SearchClickRequest(query="test")
    assert req.results_count == 0
    assert req.clicked_track_id is None


def test_search_click_query_too_long() -> None:
    with pytest.raises(ValidationError):
        SearchClickRequest(query="x" * 257)
