from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.import_job import ImportJob
from app.models.user import User
from app.services.external_providers import ProviderError
from app.services.import_service import ImportService

pytestmark = pytest.mark.anyio

_WORKER = "app.services.external_scan_worker"


async def _make_user(
    session: AsyncSession,
    telegram_id: int = 3100,
) -> User:
    user = User(
        telegram_id=telegram_id,
        username=f"u{telegram_id}",
        first_name="T",
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def test_scan_external_rejects_unknown_source(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    svc = ImportService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.scan_external_playlist(
            user.id, "bandcamp", "https://example.com"
        )

    assert exc.value.status_code == 400


@patch(
    "app.services.external_scan_worker.scan_external_playlist_task",
)
async def test_scan_external_dispatches_background_task(
    mock_task: object,
    session: AsyncSession,
) -> None:
    mock_task.kiq = AsyncMock(return_value=None)  # type: ignore[attr-defined]
    user = await _make_user(session, telegram_id=3101)

    svc = ImportService(session)
    job = await svc.scan_external_playlist(
        user.id,
        "yandex_music",
        "https://music.yandex.ru/users/u/playlists/1",
    )

    assert job.status == "scanning"
    assert job.source == "yandex_music"
    mock_task.kiq.assert_called_once_with(  # type: ignore[attr-defined]
        job.id,
        "yandex_music",
        "https://music.yandex.ru/users/u/playlists/1",
    )


@patch(
    "app.services.external_scan_worker.scan_external_playlist_task",
)
async def test_scan_external_returns_active_scanning_job(
    mock_task: object,
    session: AsyncSession,
) -> None:
    mock_task.kiq = AsyncMock(return_value=None)  # type: ignore[attr-defined]
    user = await _make_user(session, telegram_id=3104)

    svc = ImportService(session)
    first = await svc.scan_external_playlist(
        user.id,
        "yandex_music",
        "https://music.yandex.ru/users/u/playlists/1",
    )
    second = await svc.scan_external_playlist(
        user.id,
        "yandex_music",
        "https://music.yandex.ru/users/u/playlists/2",
    )

    assert first.id == second.id
    assert mock_task.kiq.call_count == 1  # type: ignore[attr-defined]


async def _run_worker_task(
    session: AsyncSession,
    job_id: int,
    source: str,
    url: str,
    scan_side_effect: object,
) -> None:
    """Call scan_external_playlist_task with the test session injected."""
    from contextlib import asynccontextmanager

    @asynccontextmanager  # type: ignore[arg-type]
    async def _fake_session_factory() -> object:
        yield session

    with (
        patch(
            "app.services.external_scan_worker.AsyncSessionLocal",
            _fake_session_factory,
        ),
        patch(
            "app.services.external_scan_worker.scan_playlist_url",
            new_callable=AsyncMock,
        ) as mock_scan,
    ):
        if isinstance(scan_side_effect, Exception):
            mock_scan.side_effect = scan_side_effect
        else:
            mock_scan.return_value = scan_side_effect

        from app.services.external_scan_worker import (
            scan_external_playlist_task,
        )

        await scan_external_playlist_task(job_id, source, url)


async def test_scan_external_worker_success(
    session: AsyncSession,
) -> None:
    user = await _make_user(session, telegram_id=3201)
    job = ImportJob(
        user_id=user.id,
        source="yandex_music",
        status="scanning",
        tracks_data={"source_url": "https://music.yandex.ru/album/1"},
    )
    session.add(job)
    await session.flush()
    await session.refresh(job)

    await _run_worker_task(
        session,
        job.id,
        "yandex_music",
        "https://music.yandex.ru/album/1",
        scan_side_effect={
            "kind": "album",
            "tracks": [
                {"title": "A", "artist": "X"},
                {"title": "B", "artist": "Y"},
            ],
        },
    )

    await session.refresh(job)
    assert job.status == "ready"
    assert job.total_tracks == 2
    assert job.tracks_data is not None
    assert len(job.tracks_data["tracks"]) == 2
    assert job.tracks_data["kind"] == "album"


async def test_scan_external_worker_provider_error(
    session: AsyncSession,
) -> None:
    user = await _make_user(session, telegram_id=3202)
    url = "https://music.yandex.ru/users/u/playlists/1"
    job = ImportJob(
        user_id=user.id,
        source="yandex_music",
        status="scanning",
        tracks_data={"source_url": url},
    )
    session.add(job)
    await session.flush()
    await session.refresh(job)

    await _run_worker_task(
        session,
        job.id,
        "yandex_music",
        url,
        scan_side_effect=ProviderError("private", "playlist is private"),
    )

    await session.refresh(job)
    assert job.status == "failed"
    assert job.tracks_data is not None
    assert job.tracks_data["error_code"] == "private"
    assert job.tracks_data["error_message"] == "playlist is private"
    assert job.tracks_data["source_url"] == url


async def test_scan_external_worker_unknown_exception(
    session: AsyncSession,
) -> None:
    user = await _make_user(session, telegram_id=3203)
    job = ImportJob(
        user_id=user.id,
        source="yandex_music",
        status="scanning",
        tracks_data={"source_url": "https://music.yandex.ru/album/1"},
    )
    session.add(job)
    await session.flush()
    await session.refresh(job)

    await _run_worker_task(
        session,
        job.id,
        "yandex_music",
        "https://music.yandex.ru/album/1",
        scan_side_effect=RuntimeError("boom"),
    )

    await session.refresh(job)
    assert job.status == "failed"
    assert job.tracks_data["error_code"] == "provider_unavailable"
