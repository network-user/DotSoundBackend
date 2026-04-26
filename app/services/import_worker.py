import httpx
import structlog
from dotsound_private_core.services import (
    MAX_IMPORT_FILE_SIZE_BYTES,
    build_internal_headers,
    download_audio_url,
    resolve_audio_extension,
)

from app.config import settings
from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.models.import_job import ImportJob
from app.models.track import Track
from app.repositories.track import TrackRepository
from app.repositories.user_track_library import (
    UserTrackLibraryRepository,
)
from app.services.audio_blob_service import AudioBlobService
from app.services.cover_worker import (
    generate_and_upload_cover,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_BOT_DOWNLOAD_TIMEOUT = 60.0


@broker.task
async def process_import_job(job_id: int) -> None:
    async with AsyncSessionLocal() as session:
        job = await session.get(ImportJob, job_id)
        if not job or job.status != "importing":
            logger.warning(
                "import_job_skip",
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

        headers = build_internal_headers(settings.bot_internal_secret)
        library_repo = UserTrackLibraryRepository(session)
        track_repo = TrackRepository(session)
        blob_service = AudioBlobService(session)

        imported_tracks: list[dict] = []

        for i, audio_info in enumerate(selected):
            if job.status == "cancelled":
                break

            file_id = audio_info.get("file_id", "")
            title = audio_info.get("title", "Unknown")
            performer = audio_info.get("performer")
            duration = audio_info.get("duration")
            file_size = audio_info.get("file_size", 0)

            logger.info(
                "importing_track",
                job_id=job_id,
                index=i,
                title=title,
            )

            if file_size and file_size > MAX_IMPORT_FILE_SIZE_BYTES:
                job.failed_tracks += 1
                imported_tracks.append(
                    {
                        "title": title,
                        "status": "skipped",
                        "reason": "file_too_large",
                    }
                )
                await session.commit()
                continue

            try:
                async with httpx.AsyncClient(
                    timeout=_BOT_DOWNLOAD_TIMEOUT
                ) as client:
                    resp = await client.post(
                        download_audio_url(settings.bot_internal_url),
                        headers=headers,
                        json={"file_id": file_id},
                    )
                    if resp.status_code != 200:
                        raise Exception(
                            f"download failed: " f"{resp.status_code}"
                        )
                    audio_bytes = resp.content

                mime = audio_info.get("mime_type", "audio/mpeg")
                ext = resolve_audio_extension(mime)

                audio_blob, _ = await blob_service.get_or_create_from_bytes(
                    audio_bytes,
                    ext,
                    mime or "audio/mpeg",
                )
                existing = (
                    await track_repo.get_active_by_uploader_and_blob_id(
                        job.user_id,
                        audio_blob.id,
                    )
                )
                if existing is not None:
                    try:
                        await library_repo.add(
                            user_id=job.user_id,
                            track_id=existing.id,
                            source="telegram",
                        )
                    except Exception as exc:
                        logger.warning(
                            "import_library_add_failed",
                            job_id=job_id,
                            track_id=existing.id,
                            error=str(exc),
                        )
                    job.completed_tracks += 1
                    imported_tracks.append(
                        {
                            "title": title,
                            "status": "deduped",
                            "track_id": existing.id,
                        }
                    )
                    logger.info(
                        "import_track_deduped",
                        job_id=job_id,
                        track_id=existing.id,
                        title=title,
                    )
                    await session.commit()
                    await session.refresh(job)
                    continue

                track = Track(
                    title=title,
                    artist=performer,
                    duration_seconds=duration,
                    source="telegram",
                    catalog_type="ugc",
                    access_mode="internal_stream",
                    source_platform="telegram",
                    imported_from="telegram",
                    file_key=None,
                    file_size_bytes=len(audio_bytes),
                    uploaded_by_id=job.user_id,
                    is_public=True,
                )
                session.add(track)
                await session.flush()
                await blob_service.attach_playback_blob(
                    track, audio_blob
                )

                try:
                    await library_repo.add(
                        user_id=job.user_id,
                        track_id=track.id,
                        source="telegram",
                    )
                except Exception as exc:
                    logger.warning(
                        "import_library_add_failed",
                        job_id=job_id,
                        track_id=track.id,
                        error=str(exc),
                    )

                await generate_and_upload_cover.kiq(track.id)

                job.completed_tracks += 1
                imported_tracks.append(
                    {
                        "title": title,
                        "status": "done",
                        "track_id": track.id,
                    }
                )
                logger.info(
                    "track_imported",
                    job_id=job_id,
                    track_id=track.id,
                    title=title,
                )
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
                            source="internal",
                        )
                    except Exception:
                        logger.warning(
                            "import_artist_link_failed",
                            track_id=track.id,
                        )
            except Exception as exc:
                job.failed_tracks += 1
                imported_tracks.append(
                    {
                        "title": title,
                        "status": "failed",
                        "reason": str(exc),
                    }
                )
                logger.error(
                    "track_import_failed",
                    job_id=job_id,
                    title=title,
                    error=str(exc),
                )

            await session.commit()
            await session.refresh(job)

        if job.status != "cancelled":
            job.status = "done"

        tracks_data = job.tracks_data or {}
        tracks_data["imported"] = imported_tracks
        job.tracks_data = tracks_data
        await session.commit()
        await session.refresh(job)

        from app.services.import_job_notifications import (
            send_import_job_finished_notification,
        )

        await send_import_job_finished_notification(
            session, job
        )

        logger.info(
            "import_job_finished",
            job_id=job_id,
            completed=job.completed_tracks,
            failed=job.failed_tracks,
        )
