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
        "audios": [
            {"file_id": "f1", "title": "Song"}
        ]
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        return_value=mock_response
    )
    mock_client.__aenter__ = AsyncMock(
        return_value=mock_client
    )
    mock_client.__aexit__ = AsyncMock(
        return_value=False
    )
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
    result = await svc.cancel_job(
        job.id, user.id
    )

    assert result.status == "cancelled"


async def test_get_job_status_not_found(
    session: AsyncSession,
) -> None:
    user = await _make_user(session)
    svc = ImportService(session)

    with pytest.raises(HTTPException) as exc:
        await svc.get_job_status(9999, user.id)

    assert exc.value.status_code == 404
