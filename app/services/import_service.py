from typing import Any

import httpx
import structlog
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.import_job import ImportJob
from app.models.user import User
from app.repositories.user import UserRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)

_BOT_TIMEOUT = 30.0


class ImportService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._user_repo = UserRepository(session)

    async def _resolve_user(
        self, user_id: int
    ) -> User:
        user = await self._user_repo.get_by_id(user_id)
        if not user:
            user = (
                await self._user_repo.get_by_telegram_id(
                    user_id
                )
            )
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return user

    def _bot_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if settings.bot_internal_secret:
            headers["X-Internal-Secret"] = (
                settings.bot_internal_secret
            )
        return headers

    async def scan_telegram_profile(
        self, user_id: int
    ) -> ImportJob:
        user = await self._resolve_user(user_id)

        active = await self._get_active_job(user.id)
        if active:
            return active

        job = ImportJob(
            user_id=user.id,
            source="telegram",
            status="scanning",
        )
        self._session.add(job)
        await self._session.flush()
        await self._session.refresh(job)

        try:
            async with httpx.AsyncClient(
                timeout=_BOT_TIMEOUT
            ) as client:
                resp = await client.get(
                    f"{settings.bot_internal_url}"
                    f"/internal/profile-audios"
                    f"/{user.telegram_id}",
                    headers=self._bot_headers(),
                )
                if resp.status_code != 200:
                    job.status = "failed"
                    job.tracks_data = {
                        "error": resp.text
                    }
                    logger.error(
                        "telegram_scan_failed",
                        status=resp.status_code,
                    )
                    return job

                data = resp.json()
        except Exception as exc:
            job.status = "failed"
            job.tracks_data = {"error": str(exc)}
            logger.error(
                "telegram_scan_error", error=str(exc)
            )
            return job

        audios = data.get("audios", [])
        job.status = "ready"
        job.total_tracks = len(audios)
        job.tracks_data = {"audios": audios}

        logger.info(
            "telegram_scan_complete",
            job_id=job.id,
            total=len(audios),
        )
        return job

    async def start_import(
        self,
        job_id: int,
        user_id: int,
        track_indices: list[int],
    ) -> ImportJob:
        user = await self._resolve_user(user_id)
        job = await self._get_job(job_id, user.id)

        if job.status not in ("ready", "importing"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Job status is {job.status}",
            )

        audios = (job.tracks_data or {}).get(
            "audios", []
        )
        selected = [
            audios[i]
            for i in track_indices
            if 0 <= i < len(audios)
        ]

        job.tracks_data = {
            "audios": audios,
            "selected": selected,
        }
        job.total_tracks = len(selected)
        job.completed_tracks = 0
        job.failed_tracks = 0
        job.status = "importing"

        from app.services.import_worker import (
            process_import_job,
        )

        await process_import_job.kiq(job.id)

        logger.info(
            "import_started",
            job_id=job.id,
            selected=len(selected),
        )
        return job

    async def get_job_status(
        self, job_id: int, user_id: int
    ) -> ImportJob:
        user = await self._resolve_user(user_id)
        return await self._get_job(job_id, user.id)

    async def get_active_job(
        self, user_id: int
    ) -> ImportJob | None:
        user = await self._resolve_user(user_id)
        return await self._get_active_job(user.id)

    async def cancel_job(
        self, job_id: int, user_id: int
    ) -> ImportJob:
        user = await self._resolve_user(user_id)
        job = await self._get_job(job_id, user.id)
        if job.status in ("importing", "scanning"):
            job.status = "cancelled"
        return job

    async def _get_job(
        self, job_id: int, internal_user_id: int
    ) -> ImportJob:
        result = await self._session.execute(
            select(ImportJob).where(
                ImportJob.id == job_id,
                ImportJob.user_id == internal_user_id,
            )
        )
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Import job not found",
            )
        return job

    async def _get_active_job(
        self, internal_user_id: int
    ) -> ImportJob | None:
        result = await self._session.execute(
            select(ImportJob)
            .where(
                ImportJob.user_id == internal_user_id,
                ImportJob.status.in_(
                    [
                        "scanning",
                        "ready",
                        "importing",
                    ]
                ),
            )
            .order_by(ImportJob.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
