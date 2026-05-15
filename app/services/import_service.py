import asyncio
import contextlib
import hashlib

import httpx
import structlog
from dotsound_private_core.services import (
    build_internal_headers,
    fetch_user_library,
    profile_audios_url,
)
from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.redis import get_redis_client
from app.models.import_job import ImportJob
from app.models.user import User
from app.models.user_linked_account import UserLinkedAccount
from app.repositories.user import UserRepository
from app.services.external_providers import (
    ProviderError,
    scan_playlist_url,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_BOT_TIMEOUT = 30.0
_SCAN_CACHE_PREFIX = "import:scan"
_CANCEL_FLAG_PREFIX = "import:cancel"


def _cancel_flag_key(job_id: int) -> str:
    return f"{_CANCEL_FLAG_PREFIX}:{job_id}"


async def set_cancel_flag(job_id: int) -> None:
    """Mark a job as cancelled in Redis.

    Worker loops poll this on every iteration so the cancel takes
    effect without the per-item ``session.refresh(job)`` round-trip
    that previously dominated the loop overhead at scale.
    """
    with contextlib.suppress(Exception):
        await get_redis_client().set(
            _cancel_flag_key(job_id),
            "1",
            ex=settings.import_cancel_flag_ttl_seconds,
        )


async def is_cancel_flag_set(job_id: int) -> bool:
    try:
        v = await get_redis_client().get(_cancel_flag_key(job_id))
        return v is not None
    except Exception:
        return False


async def clear_cancel_flag(job_id: int) -> None:
    with contextlib.suppress(Exception):
        await get_redis_client().delete(_cancel_flag_key(job_id))


def _scan_cache_key(user_id: int, source: str, url: str) -> str:
    digest = hashlib.sha256(f"{source}:{url}".encode()).hexdigest()
    return f"{_SCAN_CACHE_PREFIX}:{user_id}:{digest}"


async def _get_scan_cache_job_id(
    user_id: int, source: str, url: str
) -> int | None:
    try:
        key = _scan_cache_key(user_id, source, url)
        raw = await get_redis_client().get(key)
        if raw is None:
            return None
        return int(raw)
    except Exception:
        return None


async def _set_scan_cache(
    user_id: int, source: str, url: str, job_id: int
) -> None:
    try:
        key = _scan_cache_key(user_id, source, url)
        await get_redis_client().set(
            key,
            str(job_id),
            ex=settings.scan_url_cache_ttl_seconds,
        )
    except Exception:
        pass


def _is_postgresql(session: AsyncSession) -> bool:
    bind = session.get_bind()
    return getattr(bind.dialect, "name", "") == "postgresql"


async def _advisory_lock_user(session: AsyncSession, user_id: int) -> None:
    """Acquire a transaction-level advisory lock keyed on user_id.

    Serializes concurrent start_import calls for the same user to
    prevent the TOCTOU race in the per-user concurrency cap check.
    Releases automatically when the transaction ends. No-op on
    non-PostgreSQL dialects (e.g. SQLite in tests).
    """
    if not _is_postgresql(session):
        return
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:key)"),
        {"key": user_id},
    )


EXTERNAL_IMPORT_SOURCES: frozenset[str] = frozenset(
    {
        "yandex_music",
        "spotify",
        "soundcloud_playlist",
        "vk_music",
        # Account-based sources — resolved via OAuth tokens
        "spotify_account",
        "soundcloud_account",
        "vk_account",
    }
)


class ImportService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._user_repo = UserRepository(session)

    async def _enqueue_started_job(self, job: ImportJob) -> None:
        if job.source in EXTERNAL_IMPORT_SOURCES:
            from app.services.external_import_worker import (
                process_external_import_job,
            )

            await process_external_import_job.kiq(job.id)
            return

        from app.services.import_worker import process_import_job

        await process_import_job.kiq(job.id)

    async def _resolve_user(self, user_id: int) -> User:
        user = await self._user_repo.get_by_id(user_id)
        if not user:
            user = await self._user_repo.get_by_telegram_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return user

    async def scan_telegram_profile(self, user_id: int) -> ImportJob:
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
            async with httpx.AsyncClient(timeout=_BOT_TIMEOUT) as client:
                resp = await client.get(
                    profile_audios_url(
                        settings.bot_internal_url,
                        user.telegram_id,
                    ),
                    headers=build_internal_headers(
                        settings.bot_internal_secret
                    ),
                )
                if resp.status_code != 200:
                    job.status = "failed"
                    job.tracks_data = {"error": resp.text}
                    logger.error(
                        "telegram_scan_failed",
                        status=resp.status_code,
                    )
                    return job

                data = resp.json()
        except Exception as exc:
            job.status = "failed"
            job.tracks_data = {"error": str(exc)}
            logger.error("telegram_scan_error", error=str(exc))
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

    async def scan_external_playlist(
        self, user_id: int, source: str, url: str
    ) -> ImportJob:
        if source not in EXTERNAL_IMPORT_SOURCES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported external source: {source}",
            )

        user = await self._resolve_user(user_id)

        cached_job_id = await _get_scan_cache_job_id(user.id, source, url)
        if cached_job_id is not None:
            cached_job = await self._session.get(ImportJob, cached_job_id)
            if cached_job and cached_job.status == "ready":
                logger.info(
                    "external_scan_cache_hit",
                    job_id=cached_job_id,
                    source=source,
                )
                return cached_job

        active = await self._get_active_job(user.id)
        if active:
            return active

        job = ImportJob(
            user_id=user.id,
            source=source,
            status="scanning",
        )
        self._session.add(job)
        await self._session.flush()
        await self._session.refresh(job)

        try:
            result = await scan_playlist_url(source, url)
        except ProviderError as exc:
            job.status = "failed"
            job.tracks_data = {
                "error_code": exc.code,
                "error_message": exc.message,
                "source_url": url,
            }
            logger.info(
                "external_scan_provider_error",
                job_id=job.id,
                source=source,
                code=exc.code,
                message=exc.message,
            )
            return job
        except Exception as exc:
            job.status = "failed"
            job.tracks_data = {
                "error_code": "provider_unavailable",
                "error_message": str(exc),
                "source_url": url,
            }
            logger.error(
                "external_scan_error",
                job_id=job.id,
                source=source,
                error=str(exc),
            )
            return job

        tracks = result.get("tracks", [])
        job.status = "ready"
        job.total_tracks = len(tracks)
        job.tracks_data = {
            "kind": result.get("kind"),
            "source_url": url,
            "tracks": tracks,
        }

        logger.info(
            "external_scan_complete",
            job_id=job.id,
            source=source,
            total=len(tracks),
        )
        await _set_scan_cache(user.id, source, url, job.id)
        return job

    async def scan_account_library(
        self,
        user_id: int,
        provider: str,
        source: str,
        account: UserLinkedAccount,
    ) -> ImportJob:
        """Scan a user's personal library from a connected provider account.

        ``source`` is ``"liked"`` or an opaque playlist ID from
        :func:`~app.api.v1.linked_accounts.list_provider_playlists`.
        """
        from app.services.linked_account_service import LinkedAccountService

        job_source = f"{provider}_account"
        user = await self._resolve_user(user_id)

        active = await self._get_active_job(user.id)
        if active:
            return active

        job = ImportJob(
            user_id=user.id,
            source=job_source,
            status="scanning",
        )
        self._session.add(job)
        await self._session.flush()
        await self._session.refresh(job)

        linked_svc = LinkedAccountService(self._session)
        access_token, _ = linked_svc.get_decrypted_tokens(account)

        client_id = (
            settings.soundcloud_oauth_client_id
            if provider == "soundcloud"
            else ""
        )

        try:
            result = await asyncio.to_thread(
                fetch_user_library,
                provider,
                access_token,
                source,
                client_id=client_id,
            )
        except Exception as exc:
            job.status = "failed"
            job.tracks_data = {
                "error_code": "provider_unavailable",
                "error_message": str(exc),
            }
            logger.error(
                "account_library_scan_error",
                job_id=job.id,
                provider=provider,
                error=str(exc),
            )
            return job

        if result.status != "ok":
            job.status = "failed"
            job.tracks_data = {
                "error_code": result.status,
                "error_message": result.error_message or result.status,
            }
            logger.info(
                "account_library_scan_provider_error",
                job_id=job.id,
                provider=provider,
                code=result.status,
            )
            return job

        tracks = [
            {
                "title": t.title,
                "artist": t.artist,
                "duration_seconds": t.duration_seconds,
                "external_id": t.external_id,
            }
            for t in result.tracks
        ]
        source_label = (
            "Liked tracks" if source == "liked" else f"Playlist: {source}"
        )
        job.status = "ready"
        job.total_tracks = len(tracks)
        job.tracks_data = {
            "kind": result.kind or "playlist",
            "source_label": source_label,
            "tracks": tracks,
        }
        logger.info(
            "account_library_scan_complete",
            job_id=job.id,
            provider=provider,
            source=source,
            total=len(tracks),
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

        if job.status not in ("ready", "importing", "queued"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Job status is {job.status}",
            )

        is_external = job.source in EXTERNAL_IMPORT_SOURCES
        items_key = "tracks" if is_external else "audios"
        items = (job.tracks_data or {}).get(items_key, [])
        selected = [items[i] for i in track_indices if 0 <= i < len(items)]

        job.tracks_data = {
            **(job.tracks_data or {}),
            items_key: items,
            "selected": selected,
        }
        job.total_tracks = len(selected)
        job.completed_tracks = 0
        job.failed_tracks = 0

        await _advisory_lock_user(self._session, user.id)
        global_active = await self._count_importing_jobs()
        per_user_active = await self._count_importing_jobs(user_id=user.id)
        global_full = global_active >= settings.import_max_concurrent_jobs
        per_user_full = (
            per_user_active >= settings.import_per_user_max_concurrent
        )
        if global_full or per_user_full:
            job.status = "queued"
            await self._session.flush()
            logger.info(
                "import_queued",
                job_id=job.id,
                source=job.source,
                selected=len(selected),
                global_active=global_active,
                per_user_active=per_user_active,
                reason=("global_cap" if global_full else "per_user_cap"),
            )
            return job

        job.status = "importing"
        await self._session.flush()
        await self._session.commit()

        try:
            await self._enqueue_started_job(job)
        except Exception as exc:  # noqa: BLE001
            await self._session.refresh(job)
            if job.status == "importing":
                job.status = "queued"
                await self._session.commit()
            logger.error(
                "import_start_enqueue_failed",
                job_id=job.id,
                source=job.source,
                error=str(exc),
            )
            return job

        logger.info(
            "import_started",
            job_id=job.id,
            source=job.source,
            selected=len(selected),
        )
        return job

    async def get_queue_position(
        self, job_id: int, user_id: int
    ) -> int | None:
        user = await self._resolve_user(user_id)
        job = await self._get_job(job_id, user.id)
        if job.status != "queued":
            return None
        result = await self._session.execute(
            select(func.count())
            .select_from(ImportJob)
            .where(
                ImportJob.status == "queued",
                ImportJob.created_at <= job.created_at,
                ImportJob.id != job.id,
            )
        )
        ahead = int(result.scalar() or 0)
        return ahead + 1

    async def _count_importing_jobs(self, user_id: int | None = None) -> int:
        stmt = (
            select(func.count())
            .select_from(ImportJob)
            .where(ImportJob.status == "importing")
        )
        if user_id is not None:
            stmt = stmt.where(ImportJob.user_id == user_id)
        result = await self._session.execute(stmt)
        return int(result.scalar() or 0)

    async def get_job_status(self, job_id: int, user_id: int) -> ImportJob:
        user = await self._resolve_user(user_id)
        return await self._get_job(job_id, user.id)

    async def get_active_job(self, user_id: int) -> ImportJob | None:
        user = await self._resolve_user(user_id)
        return await self._get_active_job(user.id)

    async def cancel_job(self, job_id: int, user_id: int) -> ImportJob:
        user = await self._resolve_user(user_id)
        job = await self._get_job(job_id, user.id)
        if job.status in (
            "importing",
            "scanning",
            "ready",
            "queued",
        ):
            job.status = "cancelled"
            await set_cancel_flag(job.id)
        return job

    async def _get_job(self, job_id: int, internal_user_id: int) -> ImportJob:
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

    async def _get_active_job(self, internal_user_id: int) -> ImportJob | None:
        result = await self._session.execute(
            select(ImportJob)
            .where(
                ImportJob.user_id == internal_user_id,
                ImportJob.status.in_(
                    [
                        "scanning",
                        "ready",
                        "importing",
                        "queued",
                    ]
                ),
            )
            .order_by(ImportJob.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
