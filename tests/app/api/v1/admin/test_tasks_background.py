from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.background_job import BackgroundJob
from tests.conftest import (
    admin_bearer_for_user,
    create_test_user,
    grant_admin_capability,
)

pytestmark = pytest.mark.anyio


async def test_admin_background_job_detail_includes_playback_progress(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 130009)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=admin["id"]
    )
    await grant_admin_capability(
        db_session, admin["id"], "tasks.manage"
    )
    job = BackgroundJob(
        id="bg-progress-1",
        name=(
            "app.services.playback_repair_worker:"
            "repair_track_playback_task"
        ),
        queue="default",
        status="running",
        payload={
            "track_id": 123,
            "progress_id": "progress-123",
        },
        max_attempts=2,
        scheduled_at=datetime.now(UTC),
    )
    db_session.add(job)
    await db_session.commit()

    with patch(
        "app.services.playback_repair_progress.get_progress",
        new=AsyncMock(
            return_value={
                "progress_id": "progress-123",
                "track_id": 123,
                "stage": "verifying_current_source",
                "state": "running",
                "logs": ["loading track"],
            }
        ),
    ) as get_progress:
        r = await client.get(
            "/api/v1/admin/tasks/jobs/bg-progress-1",
            headers=headers,
        )

    assert r.status_code == 200
    body = r.json()
    assert body["progress_id"] == "progress-123"
    assert body["live"]["stage"] == "verifying_current_source"
    assert body["live"]["track_id"] == 123
    get_progress.assert_awaited_once_with("progress-123")


async def test_admin_bulk_cancel_active_background_jobs(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 130010)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=admin["id"]
    )
    await grant_admin_capability(
        db_session, admin["id"], "tasks.manage"
    )
    queued = BackgroundJob(
        id="bg-cancel-queued",
        name="app.tasks.demo",
        queue="default",
        status="queued",
        payload={},
        max_attempts=2,
        scheduled_at=datetime.now(UTC),
    )
    running = BackgroundJob(
        id="bg-cancel-running",
        name="app.tasks.demo",
        queue="default",
        status="running",
        payload={},
        max_attempts=2,
        scheduled_at=datetime.now(UTC),
    )
    done = BackgroundJob(
        id="bg-cancel-done",
        name="app.tasks.demo",
        queue="default",
        status="done",
        payload={},
        max_attempts=2,
        scheduled_at=datetime.now(UTC),
    )
    db_session.add_all([queued, running, done])
    await db_session.commit()

    with (
        patch(
            "app.api.v1.admin.tasks.signal_cancel",
            new=AsyncMock(),
        ) as signal_cancel,
        patch(
            "app.api.v1.admin.tasks._purge_bgjob_messages",
            new=AsyncMock(return_value=1),
        ) as purge,
    ):
        r = await client.post(
            "/api/v1/admin/tasks/jobs/cancel-active",
            headers=headers,
            json={"name": "demo"},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["matched"] == 2
    assert body["cancelled"] == 1
    assert body["cancelling"] == 1
    assert body["purged_messages"] == 1
    assert set(body["items"]) == {
        "bg-cancel-queued",
        "bg-cancel-running",
    }
    purge.assert_awaited_once_with({"bg-cancel-queued"})
    assert signal_cancel.await_count == 2

    await db_session.refresh(queued)
    await db_session.refresh(running)
    await db_session.refresh(done)
    assert queued.status == "cancelled"
    assert queued.finished_at is not None
    assert running.status == "cancelling"
    assert done.status == "done"


async def test_admin_playback_repair_summary_aggregates_jobs(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin = await create_test_user(client, 130010)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=admin["id"]
    )
    await grant_admin_capability(
        db_session, admin["id"], "tasks.manage"
    )
    task_name = (
        "app.services.playback_repair_worker:"
        "repair_track_playback_task"
    )
    db_session.add_all(
        [
            BackgroundJob(
                id="bg-repair-done",
                name=task_name,
                queue="default",
                status="done",
                payload={
                    "track_id": 321,
                    "progress_id": "progress-done",
                },
                result_summary={
                    "track_id": 321,
                    "ok": True,
                    "status": "repaired",
                },
                max_attempts=2,
                scheduled_at=datetime.now(UTC),
            ),
            BackgroundJob(
                id="bg-repair-running",
                name=task_name,
                queue="default",
                status="running",
                payload={
                    "track_id": 322,
                    "progress_id": "progress-running",
                },
                max_attempts=2,
                scheduled_at=datetime.now(UTC),
            ),
        ]
    )
    await db_session.commit()

    with patch(
        "app.services.playback_repair_progress.get_many_progress",
        new=AsyncMock(
            return_value={
                "progress-running": {
                    "progress_id": "progress-running",
                    "track_id": 322,
                    "stage": "refreshing_source",
                    "state": "running",
                    "updated_at": "2026-05-16T09:10:00+00:00",
                }
            }
        ),
    ) as get_many_progress:
        r = await client.post(
            "/api/v1/admin/tasks/playback-repair/summary",
            headers=headers,
            json={
                "job_ids": [
                    "bg-repair-done",
                    "bg-repair-running",
                    "missing",
                ]
            },
        )

    assert r.status_code == 200
    body = r.json()
    assert body["requested"] == 3
    assert body["matched"] == 2
    assert body["processed"] == 1
    assert body["remaining"] == 1
    assert body["statuses"]["done"] == 1
    assert body["statuses"]["running"] == 1
    assert body["outcomes"]["repaired"] == 1
    assert body["current"]["job_id"] == "bg-repair-running"
    assert body["current"]["track_id"] == 322
    assert body["current"]["stage"] == "refreshing_source"
    get_many_progress.assert_awaited_once()
    assert set(get_many_progress.await_args.args[0]) == {
        "progress-done",
        "progress-running",
    }
