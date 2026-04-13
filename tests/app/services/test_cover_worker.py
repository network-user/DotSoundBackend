from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.models.user import User

pytestmark = pytest.mark.anyio

_MOD = "app.services.cover_worker"


async def _make_track(
    session: AsyncSession,
) -> Track:
    user = User(
        telegram_id=1800,
        username="u",
        first_name="T",
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)

    track = Track(
        title="T",
        file_key="k",
        uploaded_by_id=user.id,
    )
    session.add(track)
    await session.flush()
    await session.refresh(track)
    return track


_COVER_RV = "covers/new.png"


@patch(
    f"{_MOD}.s3.upload_cover",
    new_callable=AsyncMock,
    return_value=_COVER_RV,
)
@patch(f"{_MOD}.s3.delete_object", new_callable=AsyncMock)
@patch(f"{_MOD}.AsyncSessionLocal")
async def test_generate_and_upload_cover(
    mock_session_local: AsyncMock,
    mock_delete: AsyncMock,
    mock_upload: AsyncMock,
    session: AsyncSession,
) -> None:
    track = await _make_track(session)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(
        return_value=session
    )
    mock_ctx.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_session_local.return_value = mock_ctx

    from app.services.cover_worker import (
        generate_and_upload_cover,
    )

    await generate_and_upload_cover(track.id)

    mock_upload.assert_awaited_once()


@patch(f"{_MOD}.AsyncSessionLocal")
async def test_generate_cover_track_not_found(
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

    from app.services.cover_worker import (
        generate_and_upload_cover,
    )

    await generate_and_upload_cover(9999)


@patch(
    f"{_MOD}.s3.upload_cover",
    new_callable=AsyncMock,
    return_value=_COVER_RV,
)
@patch(f"{_MOD}.s3.delete_object", new_callable=AsyncMock)
@patch(f"{_MOD}.AsyncSessionLocal")
async def test_generate_cover_replaces_old(
    mock_session_local: AsyncMock,
    mock_delete: AsyncMock,
    mock_upload: AsyncMock,
    session: AsyncSession,
) -> None:
    track = await _make_track(session)
    track.cover_key = "covers/old.png"
    await session.flush()

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(
        return_value=session
    )
    mock_ctx.__aexit__ = AsyncMock(
        return_value=False
    )
    mock_session_local.return_value = mock_ctx

    from app.services.cover_worker import (
        generate_and_upload_cover,
    )

    await generate_and_upload_cover(track.id)

    mock_delete.assert_awaited_once_with(
        "covers/old.png"
    )
