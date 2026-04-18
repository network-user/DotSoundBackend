from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.lyrics_worker import (
    generate_lyrics_task,
)


@pytest.fixture(autouse=True)
def _reset_lyrics_cache():
    with patch(
        "app.services.lyrics_worker.get_cached_lyrics_result",
        new_callable=AsyncMock,
        return_value=None,
    ), patch(
        "app.services.lyrics_worker.set_cached_lyrics_result",
        new_callable=AsyncMock,
        return_value=None,
    ):
        yield


@dataclass
class _FakeTrack:
    id: int = 1
    title: str = "test song"
    artist: str | None = "test artist"
    file_key: str | None = "tracks/1/audio.mp3"
    is_active: bool = True


@dataclass
class _FakeLyricsResult:
    text: str = "Line one\nLine two"
    synced_lines: list | None = None


@dataclass
class _FakeSyncedLine:
    time_ms: int = 0
    text: str = ""
    confidence: float | None = None


def _make_lyrics_result(
    with_sync: bool = False,
) -> _FakeLyricsResult:
    result = _FakeLyricsResult()
    if with_sync:
        result.synced_lines = [
            _FakeSyncedLine(
                time_ms=1000, text="Line one"
            ),
            _FakeSyncedLine(
                time_ms=3000, text="Line two"
            ),
        ]
    return result


@pytest.fixture
def mock_session():
    session = AsyncMock()
    return session


@pytest.fixture
def mock_db_session(mock_session):
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(
        return_value=mock_session
    )
    ctx.__aexit__ = AsyncMock(return_value=False)
    with patch(
        "app.services.lyrics_worker.AsyncSessionLocal",
        return_value=ctx,
    ):
        yield mock_session


def _setup_track_query(
    mock_session: AsyncMock,
    track: _FakeTrack | None,
) -> None:
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = (
        track
    )
    mock_session.execute = AsyncMock(
        return_value=result_mock
    )


class TestGenerateLyricsTask:
    @pytest.mark.anyio
    @patch(
        "app.services.lyrics_worker.s3.download_object",
        new_callable=AsyncMock,
        return_value=b"fake-audio-bytes",
    )
    @patch(
        "dotsound_private_core.services"
        ".lyrics_provider.generate_lyrics"
    )
    async def test_with_sync_downloads_audio(
        self,
        mock_generate: MagicMock,
        mock_s3: AsyncMock,
        mock_db_session: AsyncMock,
    ) -> None:
        track = _FakeTrack()
        _setup_track_query(mock_db_session, track)
        mock_generate.return_value = (
            _make_lyrics_result(with_sync=True)
        )

        with patch(
            "app.services.lyrics_worker"
            ".LyricsRepository"
        ) as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo_cls.return_value = mock_repo

            result = await generate_lyrics_task(
                track_id=1, with_sync=True
            )

        assert result["status"] == "found"
        assert result["has_sync"] is True
        mock_s3.assert_called_once_with(
            "tracks/1/audio.mp3"
        )
        mock_generate.assert_called_once()
        call_kwargs = mock_generate.call_args[1]
        assert call_kwargs["audio_path"] is not None

    @pytest.mark.anyio
    @patch(
        "dotsound_private_core.services"
        ".lyrics_provider.generate_lyrics"
    )
    async def test_without_sync_no_audio(
        self,
        mock_generate: MagicMock,
        mock_db_session: AsyncMock,
    ) -> None:
        track = _FakeTrack()
        _setup_track_query(mock_db_session, track)
        mock_generate.return_value = (
            _make_lyrics_result(with_sync=False)
        )

        with patch(
            "app.services.lyrics_worker"
            ".LyricsRepository"
        ) as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo_cls.return_value = mock_repo

            result = await generate_lyrics_task(
                track_id=1, with_sync=False
            )

        assert result["status"] == "found"
        assert result["has_sync"] is False
        mock_generate.assert_called_once()
        call_kwargs = mock_generate.call_args[1]
        assert call_kwargs["audio_path"] is None

    @pytest.mark.anyio
    @patch(
        "dotsound_private_core.services"
        ".lyrics_provider.generate_lyrics"
    )
    async def test_external_track_no_file_key(
        self,
        mock_generate: MagicMock,
        mock_db_session: AsyncMock,
    ) -> None:
        track = _FakeTrack(file_key=None)
        _setup_track_query(mock_db_session, track)
        mock_generate.return_value = (
            _make_lyrics_result()
        )

        with patch(
            "app.services.lyrics_worker"
            ".LyricsRepository"
        ) as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo_cls.return_value = mock_repo

            result = await generate_lyrics_task(
                track_id=1, with_sync=True
            )

        assert result["status"] == "found"
        call_kwargs = mock_generate.call_args[1]
        assert call_kwargs["audio_path"] is None

    @pytest.mark.anyio
    @patch(
        "dotsound_private_core.services"
        ".lyrics_provider.generate_lyrics",
        return_value=None,
    )
    async def test_not_found(
        self,
        mock_generate: MagicMock,
        mock_db_session: AsyncMock,
    ) -> None:
        track = _FakeTrack()
        _setup_track_query(mock_db_session, track)

        result = await generate_lyrics_task(
            track_id=1
        )

        assert result["status"] == "not_found"

    @pytest.mark.anyio
    async def test_track_not_found(
        self,
        mock_db_session: AsyncMock,
    ) -> None:
        _setup_track_query(mock_db_session, None)

        result = await generate_lyrics_task(
            track_id=999
        )

        assert result["status"] == "error"
        assert "track_not_found" in result.get(
            "detail", ""
        )

    @pytest.mark.anyio
    @patch(
        "dotsound_private_core.services"
        ".lyrics_provider.generate_lyrics",
        side_effect=RuntimeError("boom"),
    )
    async def test_exception_returns_error(
        self,
        mock_generate: MagicMock,
        mock_db_session: AsyncMock,
    ) -> None:
        track = _FakeTrack()
        _setup_track_query(mock_db_session, track)

        result = await generate_lyrics_task(
            track_id=1
        )

        assert result["status"] == "error"
