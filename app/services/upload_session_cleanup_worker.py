"""Hourly Taskiq job that aborts orphaned chunked-upload sessions.

A session is orphaned when its TTL (``expires_at``) has passed while
still in ``status='active'``. The worker:

1. Selects active expired sessions.
2. Aborts each S3 multipart upload (best-effort).
3. Marks the session ``status='expired'``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select, update

from app.config import settings
from app.core import s3
from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.models.upload_session import UploadSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@broker.task
async def cleanup_upload_sessions_task() -> dict[str, Any]:
    now = datetime.now(UTC)
    aborted = 0
    failed = 0

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UploadSession).where(
                UploadSession.status == "active",
                UploadSession.expires_at < now,
            )
        )
        sessions: list[UploadSession] = list(result.scalars().all())

        for record in sessions:
            if record.s3_multipart_id:
                try:
                    async with s3.get_s3_client() as client:
                        await client.abort_multipart_upload(
                            Bucket=settings.minio_bucket,
                            Key=record.s3_key,
                            UploadId=record.s3_multipart_id,
                        )
                    aborted += 1
                except Exception as exc:
                    failed += 1
                    logger.warning(
                        "upload_session_cleanup_abort_failed",
                        upload_id=record.upload_id,
                        error=str(exc),
                    )
            await session.execute(
                update(UploadSession)
                .where(UploadSession.id == record.id)
                .values(status="expired", updated_at=now)
            )
        await session.commit()

    summary = {
        "found": len(sessions),
        "aborted": aborted,
        "failed": failed,
    }
    logger.info("upload_sessions_cleanup", **summary)
    return summary
