from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.lyrics_worker import (
    _cached_satisfies_request,
    _cache_keys_for_track,
    _search_cache_key,
    generate_lyrics_task,
    invalidate_cached_lyrics_for_track,
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
    async def test_title_only_fallback_when_artist_mismatch(
        self,
        mock_generate: MagicMock,
        mock_db_session: AsyncMock,
    ) -> None:
        track = _FakeTrack(
            artist="wrong artist",
            title="correct title",
            file_key=None,
        )
        _setup_track_query(mock_db_session, track)
        mock_generate.side_effect = [
            None,
            _make_lyrics_result(with_sync=False),
        ]

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
        assert result["has_sync"] is False
        assert mock_generate.call_count == 2
        first_call = mock_generate.call_args_list[0][1]
        second_call = mock_generate.call_args_list[1][1]
        assert first_call["artist"] == "wrong artist"
        assert first_call["title"] == "correct title"
        assert second_call["artist"] == ""
        assert second_call["title"] == "correct title"

    @pytest.mark.anyio
    @patch(
        "dotsound_private_core.services"
        ".lyrics_provider.generate_lyrics"
    )
    async def test_bypass_cache_skips_cache_read(
        self,
        mock_generate: MagicMock,
        mock_db_session: AsyncMock,
    ) -> None:
        track = _FakeTrack()
        _setup_track_query(mock_db_session, track)
        mock_generate.return_value = _make_lyrics_result()

        with patch(
            "app.services.lyrics_worker.get_cached_lyrics_result",
            new_callable=AsyncMock,
        ) as mock_get_cached, patch(
            "app.services.lyrics_worker"
            ".LyricsRepository"
        ) as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo_cls.return_value = mock_repo
            mock_get_cached.return_value = {
                "text": "cached text that must be ignored"
            }

            result = await generate_lyrics_task(
                track_id=1,
                with_sync=False,
                bypass_cache=True,
            )

        assert result["status"] == "found"
        mock_get_cached.assert_not_awaited()
        mock_generate.assert_called_once()

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

    @pytest.mark.anyio
    @patch(
        "dotsound_private_core.services"
        ".lyrics_provider.generate_lyrics"
    )
    async def test_with_sync_skips_text_only_cache(
        self,
        mock_generate: MagicMock,
        mock_db_session: AsyncMock,
    ) -> None:
        track = _FakeTrack(file_key=None)
        _setup_track_query(mock_db_session, track)
        mock_generate.return_value = (
            _make_lyrics_result(with_sync=True)
        )

        with patch(
            "app.services.lyrics_worker.get_cached_lyrics_result",
            new_callable=AsyncMock,
        ) as mock_get_cached, patch(
            "app.services.lyrics_worker"
            ".LyricsRepository"
        ) as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo_cls.return_value = mock_repo
            mock_get_cached.return_value = {
                "text": "cached text without timecodes",
                "synced_lines": None,
            }

            result = await generate_lyrics_task(
                track_id=1,
                with_sync=True,
            )

        assert result["status"] == "found"
        assert result["has_sync"] is True
        mock_generate.assert_called_once()
        repo_call = mock_repo.create_or_update.await_args
        assert repo_call is not None
        assert repo_call.kwargs["synced_lines"] is not None
        assert (
            repo_call.kwargs["synced_lines"][0]["time_ms"]
            == 1000
        )

    @pytest.mark.anyio
    @patch(
        "dotsound_private_core.services"
        ".lyrics_provider.generate_lyrics"
    )
    async def test_with_sync_reuses_cached_synced_lines(
        self,
        mock_generate: MagicMock,
        mock_db_session: AsyncMock,
    ) -> None:
        track = _FakeTrack()
        _setup_track_query(mock_db_session, track)

        cached_payload = {
            "text": "cached text",
            "synced_lines": [
                {
                    "time_ms": 500,
                    "text": "cached line",
                    "confidence": 0.9,
                }
            ],
            "sync_quality": "line",
            "sync_profile": "cpu_light",
        }

        with patch(
            "app.services.lyrics_worker.get_cached_lyrics_result",
            new_callable=AsyncMock,
        ) as mock_get_cached, patch(
            "app.services.lyrics_worker"
            ".LyricsRepository"
        ) as mock_repo_cls, patch(
            "app.services.lyrics_worker"
            ".store_partial_synced",
            new_callable=AsyncMock,
        ) as mock_store_partial:
            mock_repo = AsyncMock()
            mock_repo_cls.return_value = mock_repo
            mock_get_cached.return_value = cached_payload

            result = await generate_lyrics_task(
                track_id=1,
                with_sync=True,
            )

        assert result["status"] == "found"
        assert result["has_sync"] is True
        assert result.get("cache") is True
        mock_generate.assert_not_called()
        repo_call = mock_repo.create_or_update.await_args
        assert repo_call is not None
        assert (
            repo_call.kwargs["synced_lines"]
            == cached_payload["synced_lines"]
        )
        mock_store_partial.assert_awaited_once()

    @pytest.mark.anyio
    @patch(
        "dotsound_private_core.services"
        ".lyrics_provider.generate_lyrics"
    )
    async def test_text_only_cache_serves_text_only_request(
        self,
        mock_generate: MagicMock,
        mock_db_session: AsyncMock,
    ) -> None:
        track = _FakeTrack()
        _setup_track_query(mock_db_session, track)

        with patch(
            "app.services.lyrics_worker.get_cached_lyrics_result",
            new_callable=AsyncMock,
        ) as mock_get_cached, patch(
            "app.services.lyrics_worker"
            ".LyricsRepository"
        ) as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo_cls.return_value = mock_repo
            mock_get_cached.return_value = {
                "text": "cached text",
            }

            result = await generate_lyrics_task(
                track_id=1,
                with_sync=False,
            )

        assert result["status"] == "found"
        assert result["has_sync"] is False
        assert result.get("cache") is True
        mock_generate.assert_not_called()


class TestCacheHelpers:
    def test_cached_satisfies_request_text_only(self) -> None:
        cached = {"text": "hello"}
        assert _cached_satisfies_request(cached, False) is True
        assert _cached_satisfies_request(cached, True) is False

    def test_cached_satisfies_request_with_sync(self) -> None:
        cached = {
            "text": "hello",
            "synced_lines": [
                {"time_ms": 0, "text": "hello"}
            ],
        }
        assert _cached_satisfies_request(cached, True) is True

    def test_cached_satisfies_request_empty_synced(
        self,
    ) -> None:
        cached = {"text": "hello", "synced_lines": []}
        assert _cached_satisfies_request(cached, True) is False

    def test_cached_satisfies_request_none(self) -> None:
        assert (
            _cached_satisfies_request(None, False) is False
        )
        assert (
            _cached_satisfies_request(None, True) is False
        )

    def test_cache_keys_for_track_includes_title_only(
        self,
    ) -> None:
        keys = _cache_keys_for_track(
            "Big Baby Tape", "STOMP"
        )
        assert _search_cache_key(
            "Big Baby Tape", "STOMP"
        ) in keys
        assert _search_cache_key("", "STOMP") in keys
        assert len(keys) == 2

    def test_cache_keys_for_track_no_artist(self) -> None:
        keys = _cache_keys_for_track("", "Some Title")
        assert keys == [_search_cache_key("", "Some Title")]


class TestInvalidateCachedLyricsForTrack:
    @pytest.mark.anyio
    async def test_deletes_artist_title_and_fallback(
        self,
    ) -> None:
        redis_client = AsyncMock()
        with patch(
            "app.services.lyrics_worker.get_redis_client",
            return_value=redis_client,
        ):
            await invalidate_cached_lyrics_for_track(
                "Big Baby Tape", "STOMP"
            )

        redis_client.delete.assert_awaited_once()
        deleted = redis_client.delete.await_args.args
        assert _search_cache_key(
            "Big Baby Tape", "STOMP"
        ) in deleted
        assert _search_cache_key("", "STOMP") in deleted

    @pytest.mark.anyio
    async def test_collapses_duplicate_keys(self) -> None:
        redis_client = AsyncMock()
        with patch(
            "app.services.lyrics_worker.get_redis_client",
            return_value=redis_client,
        ):
            await invalidate_cached_lyrics_for_track(
                "", "Just A Title"
            )

        redis_client.delete.assert_awaited_once()
        deleted = redis_client.delete.await_args.args
        assert deleted == (
            _search_cache_key("", "Just A Title"),
        )
