from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.import_job import ImportJob
from app.models.user import User
from app.services.import_service import (
    ImportService,
)

pytestmark = pytest.mark.anyio

_MOD = "app.services.import_service"


async def _make_user(
    session: AsyncSession,
    telegram_id: int = 1900,
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


async def test_scan_user_not_found(
    session: AsyncSession,
) -> None:
    svc = ImportService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.scan_telegram_profile(9999)

    assert exc.value.status_code == 404


@patch(f"{_MOD}.httpx.AsyncClient")
@patch(f"{_MOD}.profile_audios_url", return_value="http://bot/audios")
@patch(f"{_MOD}.build_internal_headers", return_value={})
async def test_scan_telegram_success(
    mock_headers: AsyncMock,
    mock_url: AsyncMock,
    mock_client_cls: AsyncMock,
    session: AsyncSession,
) -> None:
    user = await _make_user(session)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "audios": [{"file_id": "f1", "title": "Song"}]
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    svc = ImportService(session)
    job = await svc.scan_telegram_profile(user.id)

    assert job.status == "ready"
    assert job.total_tracks == 1


async def test_get_active_job_none(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    svc = ImportService(session)

    job = await svc.get_active_job(user.id)

    assert job is None


async def test_cancel_job(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    job = ImportJob(
        user_id=user.id,
        source="telegram",
        status="importing",
    )
    session.add(job)
    await session.flush()
    await session.refresh(job)

    svc = ImportService(session)
    result = await svc.cancel_job(job.id, user.id)

    assert result.status == "cancelled"


async def test_get_job_status_not_found(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    svc = ImportService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.get_job_status(9999, user.id)

    assert exc.value.status_code == 404


async def _make_ready_job(
    session: AsyncSession,
    user_id: int,
    source: str = "telegram",
) -> ImportJob:
    job = ImportJob(
        user_id=user_id,
        source=source,
        status="ready",
        total_tracks=1,
        tracks_data={"audios": [{"file_id": "f", "title": "T"}]},
    )
    session.add(job)
    await session.flush()
    await session.refresh(job)
    return job


async def _make_importing_job(
    session: AsyncSession,
    user_id: int,
    source: str = "telegram",
) -> ImportJob:
    job = ImportJob(
        user_id=user_id,
        source=source,
        status="importing",
        total_tracks=1,
        tracks_data={"audios": []},
    )
    session.add(job)
    await session.flush()
    await session.refresh(job)
    return job


@patch(
    f"{_MOD}.settings.import_max_concurrent_jobs",
    new=2,
)
@patch(
    f"{_MOD}.settings.import_per_user_max_concurrent",
    new=10,
)
async def test_start_import_queues_when_global_cap_reached(
    session: AsyncSession,
) -> None:
    u1 = await _make_user(session, telegram_id=2001)
    u2 = await _make_user(session, telegram_id=2002)
    u3 = await _make_user(session, telegram_id=2003)
    await _make_importing_job(session, u1.id)
    await _make_importing_job(session, u2.id)
    target = await _make_ready_job(session, u3.id)
    await session.commit()

    svc = ImportService(session)
    result = await svc.start_import(target.id, u3.id, [0])

    assert result.status == "queued"


@patch(
    f"{_MOD}.settings.import_max_concurrent_jobs",
    new=100,
)
@patch(
    f"{_MOD}.settings.import_per_user_max_concurrent",
    new=2,
)
async def test_start_import_queues_when_per_user_cap_reached(
    session: AsyncSession,
) -> None:
    user = await _make_user(session, telegram_id=2010)
    await _make_importing_job(session, user.id)
    await _make_importing_job(session, user.id)
    target = await _make_ready_job(session, user.id)
    await session.commit()

    svc = ImportService(session)
    result = await svc.start_import(target.id, user.id, [0])

    assert result.status == "queued"


@patch(
    f"{_MOD}.settings.import_max_concurrent_jobs",
    new=100,
)
@patch(
    f"{_MOD}.settings.import_per_user_max_concurrent",
    new=10,
)
async def test_start_import_commits_before_enqueue(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await _make_user(session, telegram_id=2015)
    target = await _make_ready_job(session, user.id)
    await session.commit()

    events: list[str] = []
    original_commit = type(session).commit

    async def commit_spy(current: AsyncSession) -> None:
        if current is session:
            events.append("commit")
        await original_commit(current)

    async def kiq_spy(job_id: int) -> None:
        assert job_id == target.id
        events.append("kiq")

    from app.services import import_worker

    monkeypatch.setattr(type(session), "commit", commit_spy)
    monkeypatch.setattr(import_worker.process_import_job, "kiq", kiq_spy)

    svc = ImportService(session)
    result = await svc.start_import(target.id, user.id, [0])

    assert result.status == "importing"
    assert events == ["commit", "kiq"]


async def test_get_queue_position_for_queued_job(
    session: AsyncSession,
) -> None:
    user = await _make_user(session, telegram_id=2020)
    older = ImportJob(
        user_id=user.id,
        source="telegram",
        status="queued",
        total_tracks=1,
    )
    target = ImportJob(
        user_id=user.id,
        source="telegram",
        status="queued",
        total_tracks=1,
    )
    session.add_all([older, target])
    await session.flush()
    await session.refresh(older)
    await session.refresh(target)
    await session.commit()

    svc = ImportService(session)
    position = await svc.get_queue_position(target.id, user.id)

    assert position == 2


async def test_cancel_queued_job(
    session: AsyncSession,
) -> None:
    user = await _make_user(session, telegram_id=2030)
    job = ImportJob(
        user_id=user.id,
        source="telegram",
        status="queued",
        total_tracks=1,
    )
    session.add(job)
    await session.flush()
    await session.refresh(job)

    svc = ImportService(session)
    result = await svc.cancel_job(job.id, user.id)

    assert result.status == "cancelled"
