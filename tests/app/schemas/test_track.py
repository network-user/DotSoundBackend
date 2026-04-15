from datetime import datetime

import pytest
from pydantic import ValidationError

from app.schemas.track import (
    AdjacentTracksResponse,
    PlaybackMode,
    PlayResponse,
    SCSearchResult,
    StreamResponse,
    TrackListResponse,
    TrackResponse,
    TrackUpdateRequest,
    TrackUploadResponse,
)


def test_track_response_valid() -> None:
    resp = TrackResponse(
        id=1,
        title="Song",
        artist="Artist",
        duration_seconds=180,
        play_count=0,
        is_active=True,
        created_at="2024-01-01T00:00:00",
    )
    assert resp.id == 1
    assert resp.title == "Song"
    assert resp.genre is None
    assert resp.processing_status == "active"
    assert resp.source == "internal"
    assert resp.catalog_type == "ugc"
    assert resp.access_mode == "internal_stream"
    assert resp.cover_url is None


def test_track_response_cover_url_computed() -> None:
    resp = TrackResponse(
        id=1,
        title="S",
        artist=None,
        duration_seconds=60,
        play_count=0,
        is_active=True,
        cover_key="covers/abc.jpg",
        created_at="2024-01-01T00:00:00",
    )
    assert resp.cover_url is not None
    assert "cover_proxy" in resp.cover_url
    assert "covers%2Fabc.jpg" in resp.cover_url


def test_track_response_cover_url_none() -> None:
    resp = TrackResponse(
        id=1,
        title="S",
        artist=None,
        duration_seconds=60,
        play_count=0,
        is_active=True,
        created_at="2024-01-01T00:00:00",
    )
    assert resp.cover_url is None


def test_track_response_provenance_fields() -> None:
    resp = TrackResponse(
        id=1,
        title="External",
        artist="Artist",
        duration_seconds=60,
        play_count=0,
        is_active=True,
        source="soundcloud",
        catalog_type="external_reference",
        access_mode="third_party_stream",
        source_platform="soundcloud",
        source_url="https://soundcloud.com/a/b",
        canonical_source_url="https://soundcloud.com/a/b",
        source_name="SoundCloud",
        created_at="2024-01-01T00:00:00",
    )
    assert resp.access_mode == "third_party_stream"
    assert resp.catalog_type == "external_reference"
    assert resp.source_platform == "soundcloud"
    assert resp.canonical_source_url == "https://soundcloud.com/a/b"


def test_track_response_missing_required() -> None:
    with pytest.raises(ValidationError):
        TrackResponse(id=1, title="S")


def test_track_list_response_valid() -> None:
    track = TrackResponse(
        id=1,
        title="S",
        artist=None,
        duration_seconds=60,
        play_count=0,
        is_active=True,
        created_at="2024-01-01T00:00:00",
    )
    resp = TrackListResponse(
        items=[track], total=1, page=1, size=10
    )
    assert resp.total == 1
    assert resp.page == 1
    assert resp.size == 10


def test_track_list_page_zero() -> None:
    with pytest.raises(ValidationError):
        TrackListResponse(
            items=[], total=0, page=0, size=10
        )


def test_track_list_size_zero() -> None:
    with pytest.raises(ValidationError):
        TrackListResponse(
            items=[], total=0, page=1, size=0
        )


def test_track_upload_response_valid() -> None:
    resp = TrackUploadResponse(
        id=1,
        title="Upload",
        artist=None,
        file_key="key.mp3",
        cover_key=None,
        duration_seconds=None,
        created_at="2024-01-01T00:00:00",
    )
    assert resp.processing_status == "processing"
    assert resp.source == "internal"
    assert resp.catalog_type == "ugc"
    assert resp.access_mode == "internal_stream"
    assert resp.is_public is True


def test_track_update_request_empty() -> None:
    req = TrackUpdateRequest()
    assert req.is_public is None


def test_track_update_request_set() -> None:
    req = TrackUpdateRequest(is_public=False)
    assert req.is_public is False


def test_stream_response_valid() -> None:
    resp = StreamResponse(
        track_id=1,
        url="https://example.com/stream",
    )
    assert resp.stream_type == "direct"
    assert resp.expires_in == 3600


def test_stream_response_custom() -> None:
    resp = StreamResponse(
        track_id=1,
        url="https://example.com/hls",
        stream_type="hls",
        expires_in=7200,
    )
    assert resp.stream_type == "hls"
    assert resp.expires_in == 7200


def test_stream_response_missing_url() -> None:
    with pytest.raises(ValidationError):
        StreamResponse(track_id=1)


def test_play_response_valid() -> None:
    resp = PlayResponse(
        track_id=1, play_count=42
    )
    assert resp.play_count == 42


def test_play_response_missing() -> None:
    with pytest.raises(ValidationError):
        PlayResponse(track_id=1)


def test_sc_search_result_valid() -> None:
    resp = SCSearchResult(
        sc_id=123,
        title="Song",
        artist="Art",
        duration_seconds=200,
        artwork_url="https://img.sc/a.jpg",
        sc_url="https://soundcloud.com/a/b",
        sc_uri="soundcloud:tracks:123",
    )
    assert resp.sc_id == 123


def test_sc_search_result_missing() -> None:
    with pytest.raises(ValidationError):
        SCSearchResult(sc_id=1, title="S")


def test_playback_mode_values() -> None:
    assert PlaybackMode.sequential == "sequential"
    assert PlaybackMode.shuffle == "shuffle"
    assert PlaybackMode.repeat_one == "repeat_one"


def test_playback_mode_invalid() -> None:
    with pytest.raises(ValueError):
        PlaybackMode("invalid")


def test_adjacent_tracks_defaults() -> None:
    resp = AdjacentTracksResponse()
    assert resp.prev_id is None
    assert resp.next_id is None


def test_adjacent_tracks_with_ids() -> None:
    resp = AdjacentTracksResponse(
        prev_id=5, next_id=7
    )
    assert resp.prev_id == 5
    assert resp.next_id == 7
