import asyncio
import uuid

import httpx
import structlog
from dotsound_private_core.services import (
    MAX_IMPORT_FILE_SIZE_BYTES,
    build_internal_headers,
    download_audio_url,
    resolve_audio_extension,
)

from app.config import settings
from app.core import s3
from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.models.import_job import ImportJob
from app.models.track import Track
from app.repositories.import_job_item import ImportJobItemRepository
from app.repositories.like import LikeRepository
from app.repositories.track import TrackRepository
from app.repositories.user_track_library import (
    UserTrackLibraryRepository,
)
from app.services.audio_blob_service import AudioBlobService
from app.services.cover_worker import (
    generate_and_upload_cover,
)
from app.services.import_service import (
    clear_cancel_flag,
    is_cancel_flag_set,
)
from app.services.transcoding import transcode_and_upload


def _lease_lost(job: ImportJob, expected_lease: str) -> bool:
    actual = (job.tracks_data or {}).get("worker_lease")
    return actual != expected_lease


logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_BOT_DOWNLOAD_TIMEOUT = 60.0

# HTTP statuses worth retrying. 5xx and 429 are transient; other 4xx
# are caller errors that won't recover by retry.
_BOT_RETRYABLE_STATUSES: frozenset[int] = frozenset({429, 500, 502, 503, 504})


async def _download_audio_with_retry(
    client: httpx.AsyncClient,
    *,
    url: str,
    headers: dict[str, str],
    file_id: str,
    job_id: int,
    title: str,
) -> bytes:
    """Download a single Telegram audio with exponential backoff.

    A transient bot/network failure used to kill that track for
    the whole import. Retrying a small number of times closes the
    timeout/502 window without paying for the rare double-download.
    Raises with the last upstream status (or wrapped network error)
    on the final failure.
    """
    max_retries = int(settings.import_telegram_download_max_retries)
    base_delay = float(
        settings.import_telegram_download_retry_base_delay_seconds
    )
    last_status: int | None = None
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = await client.post(
                url,
                headers=headers,
                json={"file_id": file_id},
            )
            if resp.status_code == 200:
                return resp.content
            last_status = resp.status_code
            if resp.status_code not in _BOT_RETRYABLE_STATUSES:
                raise Exception(f"download failed: {resp.status_code}")
        except (httpx.HTTPError, TimeoutError) as exc:
            last_exc = exc
        if attempt >= max_retries:
            break
        wait = base_delay * (2**attempt)
        logger.warning(
            "telegram_download_retry",
            job_id=job_id,
            title=title,
            attempt=attempt,
            wait_seconds=wait,
            last_status=last_status,
        )
        await asyncio.sleep(wait)
    if last_exc is not None:
        raise last_exc
    raise Exception(f"download failed: {last_status}")


@broker.task
async def process_import_job(job_id: int) -> None:
    async with AsyncSessionLocal() as session:
        job = await session.get(ImportJob, job_id)
        if not job or job.status != "importing":
            logger.warning(
                "import_job_skip",
                job_id=job_id,
                reason="not_found_or_wrong_status",
                actual_status=(job.status if job else None),
            )
            return

        existing_data = job.tracks_data or {}
        selected_full = existing_data.get("selected", [])
        if not selected_full:
            job.status = "done"
            job.total_tracks = 0
            await session.commit()
            await session.refresh(job)
            from app.services.import_job_notifications import (
                send_import_job_finished_notification,
            )

            await send_import_job_finished_notification(session, job)
            return

        items_repo = ImportJobItemRepository(session)
        await items_repo.seed_pending(job.id, selected_full)
        await session.commit()

        original_idx_list = await items_repo.list_pending_indices(job.id)
        selected = [selected_full[i] for i in original_idx_list]
        cursor_count = len(selected_full) - len(selected)

        worker_lease = uuid.uuid4().hex
        job.tracks_data = {**existing_data, "worker_lease": worker_lease}
        await session.commit()
        await session.refresh(job)

        headers = build_internal_headers(settings.bot_internal_secret)
        library_repo = UserTrackLibraryRepository(session)
        like_repo = LikeRepository(session)
        track_repo = TrackRepository(session)
        blob_service = AudioBlobService(session)

        if cursor_count > 0:
            logger.info(
                "telegram_import_resume",
                job_id=job_id,
                cursor=cursor_count,
                remaining=len(selected),
            )

        download_url = download_audio_url(settings.bot_internal_url)
        items_seen = 0
        lease_check_every = max(
            1, int(settings.import_lease_check_every_n_items)
        )
        async with httpx.AsyncClient(
            timeout=_BOT_DOWNLOAD_TIMEOUT
        ) as http_client:
            for pos, audio_info in enumerate(selected):
                original_idx = original_idx_list[pos]
                if await is_cancel_flag_set(job_id):
                    await session.refresh(job)
                    job.status = "cancelled"
                    await session.commit()
                    break
                if items_seen % lease_check_every == 0:
                    await session.refresh(job)
                    if _lease_lost(job, worker_lease):
                        logger.warning(
                            "telegram_import_lease_lost",
                            job_id=job_id,
                        )
                        return
                items_seen += 1

                file_id = audio_info.get("file_id", "")
                title = audio_info.get("title", "Unknown")
                performer = audio_info.get("performer")
                duration = audio_info.get("duration")
                file_size = audio_info.get("file_size", 0)

                logger.info(
                    "importing_track",
                    job_id=job_id,
                    index=original_idx,
                    title=title,
                )

                if file_size and file_size > MAX_IMPORT_FILE_SIZE_BYTES:
                    job.failed_tracks += 1
                    await items_repo.mark_skipped(
                        job.id,
                        original_idx,
                        title=title,
                        reason="file_too_large",
                    )
                    await session.commit()
                    continue

                try:
                    audio_bytes = await _download_audio_with_retry(
                        http_client,
                        url=download_url,
                        headers=headers,
                        file_id=file_id,
                        job_id=job_id,
                        title=title,
                    )

                    mime = audio_info.get("mime_type", "audio/mpeg")
                    ext = resolve_audio_extension(mime)

                    audio_blob, _ = (
                        await blob_service.get_or_create_from_bytes(
                            audio_bytes,
                            ext,
                            mime or "audio/mpeg",
                        )
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
                        try:
                            await like_repo.add_idempotent(
                                user_id=job.user_id,
                                track_id=existing.id,
                            )
                        except Exception as exc:
                            logger.warning(
                                "import_like_add_failed",
                                job_id=job_id,
                                track_id=existing.id,
                                error=str(exc),
                            )
                        job.completed_tracks += 1
                        await items_repo.mark_deduped(
                            job.id,
                            original_idx,
                            track_id=existing.id,
                            title=title,
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
                    await blob_service.attach_playback_blob(track, audio_blob)

                    # Schedule MP3 + HLS transcoding so the track plays on
                    # all platforms (OGG Vorbis/Opus is not supported by iOS
                    # Safari / Telegram WebView).  We write a one-off temp
                    # copy because transcode_and_upload deletes its raw_key
                    # after use and the CAS blob must not be removed.
                    try:
                        _tmp_key = (
                            f"tmp-transcode/{uuid.uuid4().hex}.{ext}"
                        )
                        await s3.upload_object(
                            _tmp_key,
                            audio_bytes,
                            mime or "audio/mpeg",
                        )
                        await transcode_and_upload.kiq(
                            track_id=track.id,
                            raw_key=_tmp_key,
                            original_filename=f"audio.{ext}",
                            source_sha256=audio_blob.content_sha256,
                        )
                    except Exception as _exc:
                        logger.warning(
                            "import_transcode_schedule_failed",
                            track_id=track.id,
                            title=title,
                            error=str(_exc),
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
                    try:
                        await like_repo.add_idempotent(
                            user_id=job.user_id,
                            track_id=track.id,
                        )
                    except Exception as exc:
                        logger.warning(
                            "import_like_add_failed",
                            job_id=job_id,
                            track_id=track.id,
                            error=str(exc),
                        )

                    await generate_and_upload_cover.kiq(track.id)

                    job.completed_tracks += 1
                    await items_repo.mark_done(
                        job.id,
                        original_idx,
                        track_id=track.id,
                        title=title,
                        artist=performer,
                        sc_url=None,
                        local_match=False,
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
                        from app.services.artist_service import (
                            ArtistService,
                        )

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
                    from app.services import (
                        track_ingest_schedule_service as _ingest,
                    )

                    await _ingest.schedule_new_track_background_jobs(
                        session,
                        track.id,
                        skip_lyrics=False,
                        catalog_payload={
                            "title": title,
                            "artist": performer,
                            "genre": None,
                        },
                    )
                except Exception as exc:
                    job.failed_tracks += 1
                    await items_repo.mark_failed(
                        job.id,
                        original_idx,
                        title=title,
                        artist=performer,
                        reason=str(exc),
                    )
                    logger.error(
                        "track_import_failed",
                        job_id=job_id,
                        title=title,
                        error=str(exc),
                    )

                await session.commit()
                await session.refresh(job)

        await session.refresh(job)
        if _lease_lost(job, worker_lease):
            logger.warning(
                "telegram_import_lease_lost_at_finalize",
                job_id=job_id,
            )
            return

        if job.status != "cancelled":
            job.status = "done"

        imported_tracks, _not_matched = await items_repo.list_for_response(
            job.id
        )
        tracks_data = job.tracks_data or {}
        tracks_data["imported"] = imported_tracks
        job.tracks_data = tracks_data
        await session.commit()
        await session.refresh(job)
        await clear_cancel_flag(job_id)

        from app.services.import_job_notifications import (
            send_import_job_finished_notification,
        )

        await send_import_job_finished_notification(session, job)

        logger.info(
            "import_job_finished",
            job_id=job_id,
            completed=job.completed_tracks,
            failed=job.failed_tracks,
        )
