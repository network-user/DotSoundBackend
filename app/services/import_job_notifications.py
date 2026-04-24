"""In-app notification when a bulk import job reaches a terminal state."""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.import_job import ImportJob
from app.repositories.user import UserRepository
from app.services.notification_service import NotificationService

logger = structlog.get_logger(__name__)

_SOURCE_RU: dict[str, str] = {
    "telegram": "Telegram",
    "yandex_music": "Яндекс.Музыка",
    "spotify": "Spotify",
    "soundcloud_playlist": "SoundCloud",
}
_SOURCE_EN: dict[str, str] = {
    "telegram": "Telegram",
    "yandex_music": "Yandex Music",
    "spotify": "Spotify",
    "soundcloud_playlist": "SoundCloud",
}


def _source_label(
    source: str, is_en: bool
) -> str:
    t = _SOURCE_EN if is_en else _SOURCE_RU
    return t.get(source, source)


async def send_import_job_finished_notification(
    session: AsyncSession,
    job: ImportJob,
) -> None:
    if job.status == "cancelled":
        return

    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(job.user_id)
    if not user:
        logger.warning(
            "import_notif_user_missing",
            job_id=job.id,
            user_id=job.user_id,
        )
        return

    is_en = (user.locale or "").lower().startswith("en")
    sl = _source_label(job.source, is_en)
    done = int(job.completed_tracks or 0)
    fail = int(job.failed_tracks or 0)
    tot = int(job.total_tracks or 0)

    if job.status == "failed" or (done == 0 and fail > 0 and tot > 0):
        ntype = "import_failed"
        if is_en:
            title = "Import failed"
            body = (
                f"Could not add tracks from {sl}."
                f" ({fail} error(s))"
            )
        else:
            title = "Импорт не удался"
            body = (
                f"Не удалось импортировать треки из {sl}."
                f" Ошибок: {fail}."
            )
    elif done == 0 and fail == 0 and tot == 0:
        ntype = "import_completed"
        if is_en:
            title = "Import complete"
            body = f"{sl}: no tracks in this import."
        else:
            title = "Импорт завершён"
            body = f"{sl}: в выборе не было треков."
    else:
        ntype = "import_completed"
        if is_en:
            title = "Import complete"
            if fail:
                body = (
                    f"{sl}: {done} track(s) added, "
                    f"{fail} could not be imported."
                )
            else:
                body = f"{sl}: {done} track(s) added to your library."
        else:
            title = "Импорт завершён"
            if fail:
                body = (
                    f"{sl}: {done} в библиотеку, "
                    f"{fail} не импортировано."
                )
            else:
                body = f"{sl}: в библиотеку добавлено {done} тр."

    notif = NotificationService(session)
    try:
        await notif.create(
            user_id=user.id,
            ntype=ntype,
            title=title,
            body=body,
            data={
                "job_id": job.id,
                "source": job.source,
                "completed": done,
                "failed": fail,
                "total": tot,
            },
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        logger.error(
            "import_notif_create_failed",
            job_id=job.id,
            error=str(exc),
        )
