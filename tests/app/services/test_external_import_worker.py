from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.import_job import ImportJob
from app.models.track import Track
from app.models.user import User

pytestmark = pytest.mark.anyio

_MOD = "app.services.external_import_worker"


async def _make_user(
    session: AsyncSession,
    telegram_id: int = 3200,
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


async def _make_job(
    session: AsyncSession,
    user_id: int,
    selected: list | None = None,
    source: str = "yandex_music",
) -> ImportJob:
    job = ImportJob(
        user_id=user_id,
        source=source,
        status="importing",
        tracks_data={"selected": selected or []},
    )
    session.add(job)
    await session.flush()
    await session.refresh(job)
    return job


def _session_ctx(session: AsyncSession) -> AsyncMock:
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


def _mock_sc_service(
    search_result: list[dict] | None = None,
    imported_track: Track | None = None,
    search_raises: Exception | None = None,
) -> MagicMock:
    sc = MagicMock()
    if search_raises is not None:
        sc.search = AsyncMock(side_effect=search_raises)
    else:
        sc.search = AsyncMock(
            return_value=search_result or []
        )
    sc.import_or_get_track = AsyncMock(
        return_value=imported_track
    )
    return sc


@patch(f"{_MOD}.AsyncSessionLocal")
async def test_worker_empty_selected_marks_done(
    mock_session_local: MagicMock,
    session: AsyncSession,
) -> None:
    user = await _make_user(session, telegram_id=3201)
    job = await _make_job(session, user.id, [])
    mock_session_local.return_value = _session_ctx(session)

    from app.services.external_import_worker import (
        process_external_import_job,
    )

    await process_external_import_job(job.id)

    await session.refresh(job)
    assert job.status == "done"


@patch(f"{_MOD}.AsyncSessionLocal")
async def test_worker_ignores_non_importing_job(
    mock_session_local: MagicMock,
    session: AsyncSession,
) -> None:
    user = await _make_user(session, telegram_id=3202)
    job = await _make_job(
        session,
        user.id,
        selected=[{"title": "X", "artist": "Y"}],
    )
    job.status = "cancelled"
    await session.commit()
    mock_session_local.return_value = _session_ctx(session)

    from app.services.external_import_worker import (
        process_external_import_job,
    )

    await process_external_import_job(job.id)

    await session.refresh(job)
    assert job.status == "cancelled"


@patch(f"{_MOD}.SoundCloudService")
@patch(f"{_MOD}.AsyncSessionLocal")
async def test_worker_match_creates_track(
    mock_session_local: MagicMock,
    mock_sc_cls: MagicMock,
    session: AsyncSession,
) -> None:
    user = await _make_user(session, telegram_id=3203)
    selected = [
        {
            "title": "Song",
            "artist": "Artist",
            "duration_seconds": 180,
        }
    ]
    job = await _make_job(session, user.id, selected)
    mock_session_local.return_value = _session_ctx(session)

    existing_track = Track(
        title="Song",
        artist="Artist",
        source="soundcloud",
        catalog_type="external_reference",
        access_mode="third_party_stream",
        source_platform="soundcloud",
        sc_url="https://soundcloud.com/artist/song",
        source_name="SoundCloud",
        is_public=True,
        uploaded_by_id=user.id,
    )
    session.add(existing_track)
    await session.flush()
    await session.refresh(existing_track)

    mock_sc_cls.return_value = _mock_sc_service(
        search_result=[
            {
                "id": 1,
                "title": "Song",
                "permalink_url": "https://soundcloud.com/artist/song",
            }
        ],
        imported_track=existing_track,
    )

    from app.services.external_import_worker import (
        process_external_import_job,
    )

    await process_external_import_job(job.id)

    await session.refresh(job)
    assert job.status == "done"
    assert job.completed_tracks == 1
    assert job.failed_tracks == 0
    imported = (job.tracks_data or {}).get("imported", [])
    assert len(imported) == 1
    assert imported[0]["track_id"] == existing_track.id

    await session.refresh(existing_track)
    assert existing_track.imported_from == "yandex_music"


@patch(f"{_MOD}.SoundCloudService")
@patch(f"{_MOD}.AsyncSessionLocal")
async def test_worker_no_match_goes_to_not_matched(
    mock_session_local: MagicMock,
    mock_sc_cls: MagicMock,
    session: AsyncSession,
) -> None:
    user = await _make_user(session, telegram_id=3204)
    selected = [
        {"title": "Obscure", "artist": "Nobody"}
    ]
    job = await _make_job(session, user.id, selected)
    mock_session_local.return_value = _session_ctx(session)

    mock_sc_cls.return_value = _mock_sc_service(
        search_result=[]
    )

    from app.services.external_import_worker import (
        process_external_import_job,
    )

    await process_external_import_job(job.id)

    await session.refresh(job)
    assert job.status == "done"
    assert job.completed_tracks == 0
    assert job.failed_tracks == 1
    not_matched = (job.tracks_data or {}).get(
        "not_matched", []
    )
    assert len(not_matched) == 1
    assert (
        not_matched[0]["reason"] == "no_soundcloud_match"
    )


@patch(f"{_MOD}.SoundCloudService")
@patch(f"{_MOD}.AsyncSessionLocal")
async def test_worker_empty_query_skipped(
    mock_session_local: MagicMock,
    mock_sc_cls: MagicMock,
    session: AsyncSession,
) -> None:
    user = await _make_user(session, telegram_id=3205)
    selected = [{"title": "", "artist": ""}]
    job = await _make_job(session, user.id, selected)
    mock_session_local.return_value = _session_ctx(session)

    sc = _mock_sc_service(search_result=[])
    mock_sc_cls.return_value = sc

    from app.services.external_import_worker import (
        process_external_import_job,
    )

    await process_external_import_job(job.id)

    await session.refresh(job)
    assert job.failed_tracks == 1
    assert sc.search.await_count == 0
    not_matched = (job.tracks_data or {}).get(
        "not_matched", []
    )
    assert not_matched[0]["reason"] == "no_query"


@patch(f"{_MOD}.SoundCloudService")
@patch(f"{_MOD}.AsyncSessionLocal")
async def test_worker_respects_cancel_between_items(
    mock_session_local: MagicMock,
    mock_sc_cls: MagicMock,
    session: AsyncSession,
) -> None:
    user = await _make_user(session, telegram_id=3206)
    selected = [
        {"title": "A", "artist": "X"},
        {"title": "B", "artist": "Y"},
    ]
    job = await _make_job(session, user.id, selected)
    mock_session_local.return_value = _session_ctx(session)

    call_count = {"n": 0}

    async def _search_side_effect(*_a, **_kw):
        call_count["n"] += 1
        if call_count["n"] == 1:
            await session.refresh(job)
            job.status = "cancelled"
            await session.commit()
        return []

    sc = MagicMock()
    sc.search = AsyncMock(side_effect=_search_side_effect)
    sc.import_or_get_track = AsyncMock()
    mock_sc_cls.return_value = sc

    from app.services.external_import_worker import (
        process_external_import_job,
    )

    await process_external_import_job(job.id)

    await session.refresh(job)
    assert job.status == "cancelled"
    assert sc.search.await_count == 1


@patch(f"{_MOD}.SoundCloudService")
@patch(f"{_MOD}.AsyncSessionLocal")
async def test_worker_handles_search_error(
    mock_session_local: MagicMock,
    mock_sc_cls: MagicMock,
    session: AsyncSession,
) -> None:
    user = await _make_user(session, telegram_id=3207)
    selected = [{"title": "A", "artist": "X"}]
    job = await _make_job(session, user.id, selected)
    mock_session_local.return_value = _session_ctx(session)

    mock_sc_cls.return_value = _mock_sc_service(
        search_raises=RuntimeError("sc down"),
    )

    from app.services.external_import_worker import (
        process_external_import_job,
    )

    await process_external_import_job(job.id)

    await session.refresh(job)
    assert job.failed_tracks == 1
    not_matched = (job.tracks_data or {}).get(
        "not_matched", []
    )
    assert not_matched[0]["reason"] == "search_error"

    result = await session.execute(select(Track))
    assert result.scalars().first() is None
