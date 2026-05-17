"""Dispatcher panel endpoints (types/pause/resume/workers/audit/purge)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_action_log import AdminActionLog
from app.models.background_job import BackgroundJob
from tests.conftest import (
    admin_bearer_for_user,
    create_test_user,
    grant_admin_capability,
)

pytestmark = pytest.mark.anyio


async def _setup_admin(
    client: AsyncClient, db_session: AsyncSession, tg_id: int
) -> tuple[int, dict[str, str]]:
    admin = await create_test_user(client, tg_id)
    headers = await admin_bearer_for_user(
        client, db_session, user_id=admin["id"]
    )
    await grant_admin_capability(db_session, admin["id"], "tasks.manage")
    return admin["id"], headers


async def test_tasks_types_aggregates_taskiq_and_compute(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, headers = await _setup_admin(client, db_session, 140101)
    now = datetime.now(UTC)
    db_session.add_all(
        [
            BackgroundJob(
                id="bg-d-1",
                name="app.tasks.demo:do_a",
                queue="default",
                status="done",
                payload={},
                max_attempts=1,
                scheduled_at=now - timedelta(hours=2),
                finished_at=now - timedelta(hours=1),
                duration_ms=2500,
            ),
            BackgroundJob(
                id="bg-d-2",
                name="app.tasks.demo:do_a",
                queue="default",
                status="failed_terminal",
                payload={},
                max_attempts=1,
                scheduled_at=now - timedelta(hours=2),
                finished_at=now - timedelta(hours=1),
                duration_ms=500,
                error="boom",
            ),
            BackgroundJob(
                id="bg-d-3",
                name="app.tasks.demo:do_b",
                queue="default",
                status="queued",
                payload={},
                max_attempts=1,
                scheduled_at=now,
            ),
        ]
    )
    await db_session.commit()

    with patch(
        "app.services.task_pause_service.list_paused_tasks",
        new=AsyncMock(return_value={}),
    ):
        r = await client.get(
            "/api/v1/admin/tasks/types?period_hours=6",
            headers=headers,
        )

    assert r.status_code == 200
    body = r.json()
    assert body["period_hours"] == 6
    items = {row["name"]: row for row in body["items"]}
    assert "app.tasks.demo:do_a" in items
    a = items["app.tasks.demo:do_a"]
    assert a["by_status"].get("done") == 1
    assert a["by_status"].get("failed_terminal") == 1
    assert a["done_period"] == 1
    assert a["failed_period"] == 1
    assert a["avg_duration_ms"] == 2500
    assert a["paused"] is False


async def test_tasks_pause_and_resume_round_trip(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin_id, headers = await _setup_admin(client, db_session, 140102)

    pause_calls: dict[str, dict] = {}

    async def _fake_pause(
        name: str,
        *,
        by_admin_id: int | None = None,
        reason: str | None = None,
    ) -> dict:
        meta = {
            "paused_at": "2026-05-17T00:00:00+00:00",
            "by_admin_id": by_admin_id,
            "reason": reason,
        }
        pause_calls[name] = meta
        return meta

    async def _fake_resume(name: str) -> bool:
        return pause_calls.pop(name, None) is not None

    with (
        patch(
            "app.services.admin_auth_service.consume_step_up",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.services.task_pause_service.pause_task",
            new=_fake_pause,
        ),
        patch(
            "app.services.task_pause_service.resume_task",
            new=_fake_resume,
        ),
    ):
        rp = await client.post(
            "/api/v1/admin/tasks/types/demo_task/pause",
            json={"reason": "test"},
            headers=headers,
        )
        rr = await client.post(
            "/api/v1/admin/tasks/types/demo_task/resume",
            headers=headers,
        )

    assert rp.status_code == 200, rp.text
    body = rp.json()
    assert body["task_name"] == "demo_task"
    assert body["paused"] is True
    assert body["meta"] == {
        "paused_at": "2026-05-17T00:00:00+00:00",
        "by_admin_id": admin_id,
        "reason": "test",
    }
    assert body["drained"] is None
    assert rr.status_code == 200
    assert rr.json()["paused"] is False
    assert rr.json()["removed"] is True

    logged = (
        (
            await db_session.execute(
                select(AdminActionLog).where(
                    AdminActionLog.action.in_(
                        ("tasks.types.pause", "tasks.types.resume")
                    )
                )
            )
        )
        .scalars()
        .all()
    )
    assert {row.action for row in logged} == {
        "tasks.types.pause",
        "tasks.types.resume",
    }


async def test_tasks_jobs_purge_only_terminal(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, headers = await _setup_admin(client, db_session, 140103)
    now = datetime.now(UTC)
    db_session.add_all(
        [
            BackgroundJob(
                id="bg-p-old-done",
                name="app.tasks.demo:cleanup",
                queue="default",
                status="done",
                payload={},
                max_attempts=1,
                scheduled_at=now - timedelta(days=3),
                created_at=now - timedelta(days=3),
            ),
            BackgroundJob(
                id="bg-p-old-active",
                name="app.tasks.demo:cleanup",
                queue="default",
                status="running",
                payload={},
                max_attempts=1,
                scheduled_at=now - timedelta(days=3),
                created_at=now - timedelta(days=3),
            ),
            BackgroundJob(
                id="bg-p-fresh-done",
                name="app.tasks.demo:cleanup",
                queue="default",
                status="done",
                payload={},
                max_attempts=1,
                scheduled_at=now,
                created_at=now,
            ),
        ]
    )
    await db_session.commit()

    with patch(
        "app.services.admin_auth_service.consume_step_up",
        new_callable=AsyncMock,
        return_value=True,
    ):
        r = await client.post(
            "/api/v1/admin/tasks/jobs/purge",
            headers=headers,
            json={
                "older_than_hours": 24,
                "statuses": [
                    "done",
                    "failed",
                    "failed_terminal",
                    "cancelled",
                ],
            },
        )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["deleted"] == 1

    remaining = (
        (
            await db_session.execute(
                select(BackgroundJob.id).where(
                    BackgroundJob.id.in_(
                        [
                            "bg-p-old-done",
                            "bg-p-old-active",
                            "bg-p-fresh-done",
                        ]
                    )
                )
            )
        )
        .scalars()
        .all()
    )
    assert set(remaining) == {"bg-p-old-active", "bg-p-fresh-done"}


async def test_tasks_jobs_purge_rejects_active_statuses(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, headers = await _setup_admin(client, db_session, 140104)
    with patch(
        "app.services.admin_auth_service.consume_step_up",
        new_callable=AsyncMock,
        return_value=True,
    ):
        r = await client.post(
            "/api/v1/admin/tasks/jobs/purge",
            headers=headers,
            json={
                "older_than_hours": 24,
                "statuses": ["queued", "running"],
            },
        )
    assert r.status_code == 400


async def test_tasks_audit_filters_by_prefix(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    admin_id, headers = await _setup_admin(client, db_session, 140105)
    now = datetime.now(UTC)
    db_session.add_all(
        [
            AdminActionLog(
                user_id=admin_id,
                action="tasks.types.pause",
                target_type="task_type",
                target_id="x",
                ip=None,
                meta=None,
                created_at=now,
            ),
            AdminActionLog(
                user_id=admin_id,
                action="users.lockout.release",
                target_type="user",
                target_id="999",
                ip=None,
                meta=None,
                created_at=now,
            ),
        ]
    )
    await db_session.commit()

    r = await client.get(
        "/api/v1/admin/tasks/audit?action_prefix=tasks.",
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    actions = {row["action"] for row in body["items"]}
    assert "tasks.types.pause" in actions
    assert "users.lockout.release" not in actions


async def test_tasks_workers_lists_compute_workers(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, headers = await _setup_admin(client, db_session, 140106)

    from app.models.compute_worker import ComputeWorker

    db_session.add(
        ComputeWorker(
            id="w-test-1",
            name="dev-worker",
            profile="cpu_light",
            token_hash="hash",
            active=True,
            max_concurrent_jobs=2,
            last_seen_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    r = await client.get("/api/v1/admin/tasks/workers", headers=headers)
    assert r.status_code == 200
    body = r.json()
    ids = [w["id"] for w in body["workers"]]
    assert "w-test-1" in ids
