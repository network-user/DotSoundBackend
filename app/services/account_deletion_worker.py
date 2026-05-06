"""Daily Taskiq job that hard-deletes users past the grace period.

Wired into ``scheduled_jobs`` by alembic migration ``0078``. The
scheduler kicks this task once a day (cron ``30 3 * * *``).
"""

from __future__ import annotations

from typing import Any

import structlog

from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.services.account_deletion_service import (
    AccountDeletionService,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@broker.task
async def hard_delete_expired_users_task() -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        svc = AccountDeletionService(session)
        summary = await svc.hard_delete_expired_users()
        await session.commit()
    logger.info(
        "account_hard_delete_task_done", **summary
    )
    return summary
