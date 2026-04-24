from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.import_job import ImportJob
from app.models.user import User

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _mock_import_finish_notification() -> object:
    with patch(
        "app.services.import_job_notifications.send_import_job_finished_notification",
        new_callable=AsyncMock,
    ) as m:
        yield m

_MOD = "app.services.import_worker"


async def _make_user(
    session: AsyncSession,
) -> User:
    user = User(
        telegram_id=2000,
        username="u",
        first_name="T",
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _make_job(
    session: AsyncSession,
    user_id: int,
    selected: list | None = None,
) -> ImportJob:
    job = ImportJob(
        user_id=user_id,
        source="telegram",
        status="importing",
        tracks_data={
            "selected": selected or [],
        },
    )
    session.add(job)
    await session.flush()
    await session.refresh(job)
    return job


@patch(f"{_MOD}.AsyncSessionLocal")
async def test_process_empty_selected(
    mock_session_local: AsyncMock,
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    job = await _make_job(session, user.id, [])

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(
        return_value=session
    )
    mock_ctx.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_session_local.return_value = mock_ctx

    from app.services.import_worker import (
        process_import_job,
    )

    await process_import_job(job.id)

    await session.refresh(job)
    assert job.status == "done"


@patch(f"{_MOD}.AsyncSessionLocal")
async def test_process_job_not_found(
    mock_session_local: AsyncMock,
    session: AsyncSession,
) -> None:
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(
        return_value=session
    )
    mock_ctx.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_session_local.return_value = mock_ctx

    from app.services.import_worker import (
        process_import_job,
    )

    await process_import_job(9999)


@patch(f"{_MOD}.AsyncSessionLocal")
async def test_process_wrong_status(
    mock_session_local: AsyncMock,
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    job = ImportJob(
        user_id=user.id,
        source="telegram",
        status="done",
    )
    session.add(job)
    await session.flush()
    await session.refresh(job)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(
        return_value=session
    )
    mock_ctx.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_session_local.return_value = mock_ctx

    from app.services.import_worker import (
        process_import_job,
    )

    await process_import_job(job.id)

    await session.refresh(job)
    assert job.status == "done"


@patch(f"{_MOD}.generate_and_upload_cover")
@patch(f"{_MOD}.upload_audio", new_callable=AsyncMock)
@patch(f"{_MOD}.httpx.AsyncClient")
@patch(f"{_MOD}.AsyncSessionLocal")
async def test_process_imports_track(
    mock_session_local: AsyncMock,
    mock_httpx_cls: AsyncMock,
    mock_upload: AsyncMock,
    mock_cover: AsyncMock,
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    selected = [
        {
            "file_id": "abc",
            "title": "Song1",
            "performer": "Artist",
            "duration": 120,
            "file_size": 1000,
        }
    ]
    job = await _make_job(
        session, user.id, selected
    )

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(
        return_value=session
    )
    mock_ctx.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_session_local.return_value = mock_ctx

    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.content = b"\xff\xfb" + b"\x00" * 50

    http_client = AsyncMock()
    http_client.post = AsyncMock(
        return_value=mock_resp
    )
    http_client.__aenter__ = AsyncMock(
        return_value=http_client
    )
    http_client.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_httpx_cls.return_value = http_client

    mock_upload.return_value = "audio/key.mp3"
    mock_cover.kiq = AsyncMock()

    from app.services.import_worker import (
        process_import_job,
    )

    await process_import_job(job.id)

    await session.refresh(job)
    assert job.status == "done"
    assert job.completed_tracks == 1


@patch(f"{_MOD}.AsyncSessionLocal")
async def test_process_skips_large_file(
    mock_session_local: AsyncMock,
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    selected = [
        {
            "file_id": "abc",
            "title": "Big",
            "file_size": 999_999_999,
        }
    ]
    job = await _make_job(
        session, user.id, selected
    )

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(
        return_value=session
    )
    mock_ctx.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_session_local.return_value = mock_ctx

    from app.services.import_worker import (
        process_import_job,
    )

    await process_import_job(job.id)

    await session.refresh(job)
    assert job.failed_tracks == 1


@patch(f"{_MOD}.upload_audio", new_callable=AsyncMock)
@patch(f"{_MOD}.httpx.AsyncClient")
@patch(f"{_MOD}.AsyncSessionLocal")
async def test_process_handles_download_fail(
    mock_session_local: AsyncMock,
    mock_httpx_cls: AsyncMock,
    mock_upload: AsyncMock,
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    selected = [
        {
            "file_id": "fail",
            "title": "Fail",
            "file_size": 1000,
        }
    ]
    job = await _make_job(
        session, user.id, selected
    )

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(
        return_value=session
    )
    mock_ctx.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_session_local.return_value = mock_ctx

    mock_resp = AsyncMock()
    mock_resp.status_code = 500

    http_client = AsyncMock()
    http_client.post = AsyncMock(
        return_value=mock_resp
    )
    http_client.__aenter__ = AsyncMock(
        return_value=http_client
    )
    http_client.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_httpx_cls.return_value = http_client

    from app.services.import_worker import (
        process_import_job,
    )

    await process_import_job(job.id)

    await session.refresh(job)
    assert job.failed_tracks == 1
