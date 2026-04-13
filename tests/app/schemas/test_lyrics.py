from datetime import datetime

import pytest
from pydantic import ValidationError

from app.schemas.lyrics import (
    LyricsCreateRequest,
    LyricsResponse,
    LyricsSyncRequest,
    SyncedLine,
)


def test_synced_line_valid() -> None:
    line = SyncedLine(time_ms=1000, text="Hello")
    assert line.time_ms == 1000
    assert line.text == "Hello"


def test_synced_line_zero_time() -> None:
    line = SyncedLine(time_ms=0, text="Start")
    assert line.time_ms == 0


def test_synced_line_negative_time() -> None:
    with pytest.raises(ValidationError):
        SyncedLine(time_ms=-1, text="Bad")


def test_synced_line_missing_text() -> None:
    with pytest.raises(ValidationError):
        SyncedLine(time_ms=0)


def test_lyrics_create_valid() -> None:
    req = LyricsCreateRequest(
        plain_text="Line one\nLine two"
    )
    assert "Line one" in req.plain_text


def test_lyrics_create_too_long() -> None:
    with pytest.raises(ValidationError):
        LyricsCreateRequest(
            plain_text="x" * 10001
        )


def test_lyrics_create_max_length() -> None:
    req = LyricsCreateRequest(
        plain_text="x" * 10000
    )
    assert len(req.plain_text) == 10000


def test_lyrics_create_empty() -> None:
    req = LyricsCreateRequest(plain_text="")
    assert req.plain_text == ""


def test_lyrics_create_missing() -> None:
    with pytest.raises(ValidationError):
        LyricsCreateRequest()


def test_lyrics_sync_sorted() -> None:
    req = LyricsSyncRequest(
        synced_lines=[
            SyncedLine(time_ms=0, text="A"),
            SyncedLine(time_ms=100, text="B"),
            SyncedLine(time_ms=200, text="C"),
        ]
    )
    assert len(req.synced_lines) == 3


def test_lyrics_sync_unsorted() -> None:
    with pytest.raises(ValidationError) as exc_info:
        LyricsSyncRequest(
            synced_lines=[
                SyncedLine(time_ms=200, text="C"),
                SyncedLine(time_ms=100, text="B"),
            ]
        )
    assert "sorted" in str(exc_info.value)


def test_lyrics_sync_equal_timestamps() -> None:
    req = LyricsSyncRequest(
        synced_lines=[
            SyncedLine(time_ms=100, text="A"),
            SyncedLine(time_ms=100, text="B"),
        ]
    )
    assert len(req.synced_lines) == 2


def test_lyrics_sync_single_line() -> None:
    req = LyricsSyncRequest(
        synced_lines=[
            SyncedLine(time_ms=0, text="Only"),
        ]
    )
    assert len(req.synced_lines) == 1


def test_lyrics_sync_empty() -> None:
    req = LyricsSyncRequest(synced_lines=[])
    assert req.synced_lines == []


def test_lyrics_response_valid() -> None:
    now = datetime(2024, 1, 1)
    resp = LyricsResponse(
        track_id=1,
        plain_text="Hello world",
        created_at=now,
        updated_at=now,
    )
    assert resp.track_id == 1
    assert resp.synced_lines is None


def test_lyrics_response_with_synced() -> None:
    now = datetime(2024, 1, 1)
    resp = LyricsResponse(
        track_id=1,
        plain_text="Hi",
        synced_lines=[
            SyncedLine(time_ms=0, text="Hi"),
        ],
        created_at=now,
        updated_at=now,
    )
    assert len(resp.synced_lines) == 1


def test_lyrics_response_missing_field() -> None:
    with pytest.raises(ValidationError):
        LyricsResponse(track_id=1)
