import difflib

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.models.import_job import ImportJob
from app.models.track import Track
from app.repositories.user_track_library import (
    UserTrackLibraryRepository,
)
from app.services.soundcloud_service import SoundCloudService

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_DURATION_TOLERANCE = 0.20
_MIN_TITLE_SCORE = 0.55
_SEARCH_LIMIT = 10


def _build_query(title: str, artist: str) -> str:
    parts = [p.strip() for p in (artist, title) if p and p.strip()]
    return " ".join(parts)


def _title_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a.casefold(), b.casefold()).ratio()


def _pick_best_sc_match(
    candidates: list[dict],
    target_title: str,
    target_duration_s: int | None,
) -> dict | None:
    """Return the best SoundCloud candidate, or None if nothing fits.

    Rules (per user spec):
      - Duration within ±20% of target when target is known
        (mandatory filter).
      - Title similarity ≥ ``_MIN_TITLE_SCORE`` (required).
      - Artist is intentionally NOT filtered — SoundCloud metadata
        is inconsistent, uploaders often rename artist.
    """
    best: dict | None = None
    best_score = -1.0
    for cand in candidates:
        duration_ms = cand.get("duration")
        if target_duration_s and duration_ms:
            duration_s = float(duration_ms) / 1000.0
            delta = abs(duration_s - target_duration_s) / (
                target_duration_s or 1
            )
            if delta > _DURATION_TOLERANCE:
                continue
        score = _title_similarity(target_title, cand.get("title") or "")
        if score > best_score:
            best_score = score
            best = cand
    if best is None or best_score < _MIN_TITLE_SCORE:
        return None
    return best


@broker.task
async def process_external_import_job(job_id: int) -> None:
    async with AsyncSessionLocal() as session:
        job = await session.get(ImportJob, job_id)
        if not job or job.status != "importing":
            logger.warning(
                "external_import_skip",
                job_id=job_id,
                reason="not_found_or_wrong_status",
            )
            return

        selected = (job.tracks_data or {}).get("selected", [])
        if not selected:
            job.status = "done"
            job.total_tracks = 0
            await session.commit()
            await session.refresh(job)
            from app.services.import_job_notifications import (
                send_import_job_finished_notification,
            )

            await send_import_job_finished_notification(
                session, job
            )
            return

        sc_service = SoundCloudService(settings.sc_client_id, session)
        library_repo = UserTrackLibraryRepository(session)
        imported: list[dict] = []
        not_matched: list[dict] = []

        for item in selected:
            await session.refresh(job)
            if job.status == "cancelled":
                break

            title = (item.get("title") or "").strip()
            artist = (item.get("artist") or "").strip()
            target_duration = item.get("duration_seconds")
            query = _build_query(title, artist)

            if not query:
                job.failed_tracks += 1
                not_matched.append(
                    {
                        "title": title or "Unknown",
                        "artist": artist or None,
                        "reason": "no_query",
                    }
                )
                await session.commit()
                continue

            try:
                results = await sc_service.search(query, limit=_SEARCH_LIMIT)
            except Exception as exc:
                logger.error(
                    "external_import_search_failed",
                    job_id=job_id,
                    query=query,
                    error=str(exc),
                )
                await session.refresh(job)
                job.failed_tracks += 1
                not_matched.append(
                    {
                        "title": title,
                        "artist": artist or None,
                        "reason": "search_error",
                    }
                )
                await session.commit()
                continue

            best_match = _pick_best_sc_match(
                results,
                target_title=title,
                target_duration_s=(
                    int(target_duration)
                    if isinstance(target_duration, (int, float))
                    else None
                ),
            )
            # Title-only retry when the first (artist+title) query
            # returned candidates but none fit. SoundCloud uploads
            # often have artist baked into the title, making the
            # combined query miss.
            if best_match is None and artist and results:
                try:
                    results_title_only = await sc_service.search(
                        title, limit=_SEARCH_LIMIT
                    )
                    best_match = _pick_best_sc_match(
                        results_title_only,
                        target_title=title,
                        target_duration_s=(
                            int(target_duration)
                            if isinstance(target_duration, (int, float))
                            else None
                        ),
                    )
                except Exception:
                    logger.debug(
                        "external_import_title_retry_failed",
                        job_id=job_id,
                    )

            if best_match is None:
                job.failed_tracks += 1
                not_matched.append(
                    {
                        "title": title,
                        "artist": artist or None,
                        "reason": "no_soundcloud_match",
                    }
                )
                await session.commit()
                continue

            try:
                try:
                    track = await sc_service.import_or_get_track(
                        sc_data=best_match,
                        uploader_id=job.user_id,
                        is_public=True,
                        skip_background_lyrics=True,
                    )
                except IntegrityError as exc:
                    await session.rollback()
                    logger.warning(
                        "external_import_dedup_race",
                        job_id=job_id,
                        error=str(exc),
                    )
                    fallback_url = best_match.get("permalink_url")
                    if not fallback_url:
                        raise
                    fallback_result = await session.execute(
                        select(Track).where(Track.sc_url == fallback_url)
                    )
                    fallback_track = fallback_result.scalar_one_or_none()
                    if fallback_track is None:
                        raise
                    track = fallback_track
                dirty = False
                if track.imported_from != job.source:
                    track.imported_from = job.source
                    dirty = True
                incoming_external_id = item.get("external_id")
                if incoming_external_id and not track.external_id:
                    track.external_id = str(incoming_external_id)
                    dirty = True
                if dirty:
                    try:
                        await session.commit()
                    except IntegrityError as exc:
                        await session.rollback()
                        logger.warning(
                            "external_import_external_id_race",
                            job_id=job_id,
                            track_id=track.id,
                            error=str(exc),
                        )

                try:
                    await library_repo.add(
                        user_id=job.user_id,
                        track_id=track.id,
                        source=job.source,
                    )
                    await session.commit()
                except Exception as exc:
                    await session.rollback()
                    logger.warning(
                        "external_import_library_add_failed",
                        job_id=job_id,
                        track_id=track.id,
                        error=str(exc),
                    )

                await session.refresh(job)
                job.completed_tracks += 1
                imported.append(
                    {
                        "title": track.title,
                        "artist": track.artist,
                        "track_id": track.id,
                        "sc_url": track.sc_url,
                        "status": "done",
                    }
                )
                await session.commit()
                from app.services.search_index_notify import (
                    schedule_reindex_track,
                )

                await schedule_reindex_track(track.id)
                if track.artist:
                    from app.services.artist_service import ArtistService

                    artist_svc = ArtistService(session)
                    try:
                        await artist_svc.resolve_and_link(
                            track_id=track.id,
                            raw_artist_string=track.artist,
                            source=track.source_platform or "soundcloud",
                        )
                        await session.commit()
                    except Exception:
                        logger.warning(
                            "external_import_artist_link_failed",
                            track_id=track.id,
                        )
                        await session.rollback()
                logger.info(
                    "external_import_track_done",
                    job_id=job_id,
                    track_id=track.id,
                    source=job.source,
                )
            except Exception as exc:
                logger.error(
                    "external_import_track_failed",
                    job_id=job_id,
                    query=query,
                    error=str(exc),
                )
                await session.refresh(job)
                job.failed_tracks += 1
                not_matched.append(
                    {
                        "title": title,
                        "artist": artist or None,
                        "reason": f"import_error: {exc}",
                    }
                )
                await session.commit()

        await session.refresh(job)
        if job.status != "cancelled":
            job.status = "done"

        job.tracks_data = {
            **(job.tracks_data or {}),
            "imported": imported,
            "not_matched": not_matched,
        }
        await session.commit()
        await session.refresh(job)

        from app.services.import_job_notifications import (
            send_import_job_finished_notification,
        )

        await send_import_job_finished_notification(
            session, job
        )

        logger.info(
            "external_import_finished",
            job_id=job_id,
            source=job.source,
            completed=job.completed_tracks,
            failed=job.failed_tracks,
        )

        if imported and job.status == "done":
            # Local import keeps the module-load graph simple and
            # prevents a theoretical circular import on backend
            # startup. Fire-and-forget: the lyrics orchestrator
            # reads the job row itself and paces per-track work.
            from app.services.import_lyrics_worker import (
                process_import_lyrics_task,
            )

            try:
                await process_import_lyrics_task.kiq(job_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "import_lyrics_enqueue_failed",
                    job_id=job_id,
                    error=str(exc),
                )
