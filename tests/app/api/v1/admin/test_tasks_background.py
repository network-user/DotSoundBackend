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
