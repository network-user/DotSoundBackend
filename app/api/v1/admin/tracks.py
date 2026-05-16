"""Admin endpoints for track management."""

import structlog
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.dependencies import (
    get_db,
    require_admin_session,
)
from app.models.user import User
from app.schemas.admin_playback import (
    AdminPlaybackRepairBulkRequest,
    AdminPlaybackRepairBulkResponse,
    AdminPlaybackRepairEnqueueResponse,
    AdminPlaybackVerifyResponse,
    AdminSoundCloudEncryptedUnsupportedCleanupRequest,
    AdminSoundCloudEncryptedUnsupportedCleanupResponse,
    AdminSoundCloudPlaybackAuditRequest,
)
from app.schemas.track import TrackUpdateRequest
from app.services.admin_lyrics_import_service import (
    AdminLyricsImportService,
)
from app.services.admin_service import AdminService
from app.services.admin_track_context_service import (
    AdminTrackContextService,
    TrackNotFoundError,
)
from app.services.admin_track_genre_mood_import_service import (
    AdminTrackGenreMoodImportService,
)
from app.services.transcoding import transcode_hls_only

from .schemas import (
    AdminIdSelectionResponse,
    AdminTrackGenrePatchRequest,
    AdminTrackListResponse,
    AdminTrackResponse,
    BatchImportRequest,
    BatchImportResponse,
    BatchPromptRequest,
    BatchPromptResponse,
    GenreMoodBatchImportRequest,
    GenreMoodBatchImportResponse,
    GenreMoodBatchPromptRequest,
    GenreMoodBatchPromptResponse,
    LyricsBatchImportRequest,
    LyricsBatchImportResponse,
    LyricsBatchPromptRequest,
    LyricsBatchPromptResponse,
    SinglePromptResponse,
    TrackContextResponse,
    TrackContextUpdateRequest,
)

router = APIRouter()
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_MAX_COVER_BYTES = 5 * 1024 * 1024
_ALLOWED_COVER_CT = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
    }
)


async def _admin_track_responses(
    service: AdminService,
    tracks: list[object],
) -> list[AdminTrackResponse]:
    rows = [AdminTrackResponse.model_validate(t) for t in tracks]
    diagnostics = await service.get_playback_failure_diagnostics(
        [row.id for row in rows],
    )
    return [
        row.model_copy(update=diagnostics.get(row.id, {}))
        for row in rows
    ]


@router.get(
    "/tracks",
    response_model=AdminTrackListResponse,
    summary="[Admin] List all tracks including hidden",
)
@limiter.limit("60/minute")
async def admin_list_tracks(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    is_active: bool | None = Query(None),
    without_lyrics: bool = Query(False),
    lyrics_catalog_miss_only: bool = Query(
        False,
        description=(
            "Tracks where automated catalog lyric lookup finished "
            "without text"
        ),
    ),
    search: str | None = Query(None, max_length=128),
    for_playlist_owner_id: int | None = Query(
        None,
        ge=1,
        description=(
            "When set, restrict to catalog + this user's uploads "
            "as for playlist add-picker"
        ),
    ),
    playable_only: bool = Query(
        False,
        description=(
            "With for_playlist_owner_id: require playable rows; alone: "
            "all active tracks that pass listing playability"
        ),
    ),
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> AdminTrackListResponse:
    service = AdminService(session)
    tracks, total = await service.list_tracks(
        page=page,
        size=size,
        is_active=is_active,
        without_lyrics=without_lyrics,
        lyrics_catalog_miss_only=lyrics_catalog_miss_only,
        search=search,
        for_playlist_owner_id=for_playlist_owner_id,
        playable_only=playable_only,
    )
    return AdminTrackListResponse(
        items=await _admin_track_responses(service, tracks),
        total=total,
        page=page,
        size=size,
    )


@router.get(
    "/tracks/ids",
    response_model=AdminIdSelectionResponse,
    summary="[Admin] List track IDs matching the current table filters",
)
@limiter.limit("30/minute")
async def admin_list_track_ids(
    request: Request,
    scope: str = Query(
        "all",
        description=(
            "One of all, playback_failures, playback_suppressed, "
            "sc_encrypted_unsupported, deleted"
        ),
    ),
    is_active: bool | None = Query(None),
    without_lyrics: bool = Query(False),
    lyrics_catalog_miss_only: bool = Query(False),
    search: str | None = Query(None, max_length=128),
    playback_error: str | None = Query(None, max_length=160),
    for_playlist_owner_id: int | None = Query(None, ge=1),
    playable_only: bool = Query(False),
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> AdminIdSelectionResponse:
    service = AdminService(session)
    if scope == "all":
        ids, total = await service.list_track_ids(
            is_active=is_active,
            without_lyrics=without_lyrics,
            lyrics_catalog_miss_only=lyrics_catalog_miss_only,
            search=search,
            for_playlist_owner_id=for_playlist_owner_id,
            playable_only=playable_only,
        )
    elif scope == "playback_failures":
        ids, total = await service.list_track_ids_playback_unavailable(
            search=search,
            playback_error=(
                playback_error.strip() if playback_error else None
            ),
        )
    elif scope == "playback_suppressed":
        ids, total = await service.list_track_ids_playback_suppressed(
            search=search,
        )
    elif scope == "sc_encrypted_unsupported":
        ids, total = await (
            service.list_track_ids_soundcloud_encrypted_unsupported(
                search=search
            )
        )
    elif scope == "deleted":
        ids, total = await service.list_deleted_track_ids(search=search)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid track id selection scope",
        )
    return AdminIdSelectionResponse(ids=ids, total=total)


@router.get(
    "/tracks/playback-health/unavailable",
    response_model=AdminTrackListResponse,
    summary="[Admin] Tracks with recorded playback fetch failures",
)
@limiter.limit("60/minute")
async def admin_list_playback_unavailable_tracks(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    search: str | None = Query(None, max_length=128),
    playback_error: str | None = Query(None, max_length=160),
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> AdminTrackListResponse:
    service = AdminService(session)
    tracks, total = await service.list_tracks_playback_unavailable(
        page=page,
        size=size,
        search=search,
        playback_error=(
            playback_error.strip() if playback_error else None
        ),
    )
    return AdminTrackListResponse(
        items=await _admin_track_responses(service, tracks),
        total=total,
        page=page,
        size=size,
    )


@router.get(
    "/tracks/playback-health/soundcloud-encrypted-unsupported",
    response_model=AdminTrackListResponse,
    summary="[Admin] SoundCloud rows blocked by encrypted HLS playback",
)
@limiter.limit("60/minute")
async def admin_list_soundcloud_encrypted_unsupported_tracks(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    search: str | None = Query(None, max_length=128),
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> AdminTrackListResponse:
    service = AdminService(session)
    tracks, total = await (
        service.list_tracks_soundcloud_encrypted_unsupported(
            page=page,
            size=size,
            search=search,
        )
    )
    return AdminTrackListResponse(
        items=await _admin_track_responses(service, tracks),
        total=total,
        page=page,
        size=size,
    )


@router.get(
    "/tracks/playback-health/suppressed",
    response_model=AdminTrackListResponse,
    summary="[Admin] Tracks auto-suppressed from public playback feeds",
)
@limiter.limit("60/minute")
async def admin_list_playback_suppressed_tracks(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    search: str | None = Query(None, max_length=128),
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> AdminTrackListResponse:
    service = AdminService(session)
    tracks, total = await service.list_tracks_playback_suppressed(
        page=page,
        size=size,
        search=search,
    )
    return AdminTrackListResponse(
        items=await _admin_track_responses(service, tracks),
        total=total,
        page=page,
        size=size,
    )


@router.post(
    "/tracks/{track_id}/playback-health/clear-suppression",
    response_model=AdminTrackResponse,
    summary="[Admin] Clear auto playback suppression window",
)
@limiter.limit("60/minute")
async def admin_clear_track_playback_suppression(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> AdminTrackResponse:
    service = AdminService(session)
    track = await service.clear_track_playback_suppression(track_id)
    if track is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    logger.info(
        "admin_playback_suppression_cleared",
        track_id=track_id,
    )
    return AdminTrackResponse.model_validate(track)


@router.post(
    "/tracks/{track_id}/playback-health/verify",
    response_model=AdminPlaybackVerifyResponse,
    summary=(
        "[Admin] Try resolving remote stream (no health log write); "
        "internal tracks only check file presence"
    ),
)
@limiter.limit("30/minute")
async def admin_verify_track_playback(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> AdminPlaybackVerifyResponse:
    service = AdminService(session)
    result = await service.verify_track_playback(track_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    logger.info(
        "admin_playback_verify",
        track_id=track_id,
        ok=result.ok,
    )
    return result


@router.post(
    "/tracks/{track_id}/playback-health/repair",
    response_model=AdminPlaybackRepairEnqueueResponse,
    summary="[Admin] Queue background playback source repair",
)
@limiter.limit("30/minute")
async def admin_repair_track_playback(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin_session),
) -> AdminPlaybackRepairEnqueueResponse:
    service = AdminService(session)
    result = await service.enqueue_track_playback_repair(
        track_id,
        actor_id=admin.id,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    logger.info(
        "admin_playback_repair_queued",
        track_id=track_id,
        queued=result.queued,
        job_id=result.job_id,
    )
    return result


@router.post(
    "/tracks/playback-health/repair",
    response_model=AdminPlaybackRepairBulkResponse,
    summary="[Admin] Queue background playback source repair for many tracks",
)
@limiter.limit("10/minute")
async def admin_repair_tracks_playback(
    request: Request,
    body: AdminPlaybackRepairBulkRequest,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin_session),
) -> AdminPlaybackRepairBulkResponse:
    service = AdminService(session)
    result = await service.enqueue_tracks_playback_repair(
        body.track_ids,
        actor_id=admin.id,
    )
    logger.info(
        "admin_playback_repair_bulk_queued",
        requested=result.requested,
        queued=result.queued,
        skipped=result.skipped,
        missing=result.missing,
    )
    return result


@router.post(
    "/tracks/playback-health/audit-soundcloud",
    response_model=AdminPlaybackRepairBulkResponse,
    summary="[Admin] Queue playback audit for imported SoundCloud tracks",
)
@limiter.limit("5/minute")
async def admin_audit_soundcloud_playback(
    request: Request,
    body: AdminSoundCloudPlaybackAuditRequest,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin_session),
) -> AdminPlaybackRepairBulkResponse:
    service = AdminService(session)
    result = await service.enqueue_soundcloud_playback_audit(
        body,
        actor_id=admin.id,
    )
    logger.info(
        "admin_soundcloud_playback_audit_queued",
        requested=result.requested,
        queued=result.queued,
        skipped=result.skipped,
        missing=result.missing,
        include_recently_checked=body.include_recently_checked,
    )
    return result


@router.post(
    "/tracks/playback-health/cleanup-soundcloud-encrypted-unsupported",
    response_model=AdminSoundCloudEncryptedUnsupportedCleanupResponse,
    summary=(
        "[Admin] Hide old SoundCloud official embeds that cannot play in "
        "DotSound"
    ),
)
@limiter.limit("5/minute")
async def admin_cleanup_soundcloud_encrypted_unsupported(
    request: Request,
    body: AdminSoundCloudEncryptedUnsupportedCleanupRequest,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin_session),
) -> AdminSoundCloudEncryptedUnsupportedCleanupResponse:
    service = AdminService(session)
    result = await service.cleanup_soundcloud_encrypted_unsupported_embeds(
        body,
        actor_id=admin.id,
    )
    logger.info(
        "admin_soundcloud_encrypted_unsupported_cleanup",
        matched=result.matched,
        updated=result.updated,
        dry_run=result.dry_run,
    )
    return result


@router.post(
    "/tracks/{track_id}/playback-health/clear-diagnostics",
    response_model=AdminTrackResponse,
    summary="[Admin] Clear playback failure summary fields on track row",
)
@limiter.limit("60/minute")
async def admin_clear_track_playback_diagnostics(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> AdminTrackResponse:
    service = AdminService(session)
    track = await service.clear_track_playback_diagnostics(track_id)
    if track is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    logger.info(
        "admin_playback_diagnostics_cleared",
        track_id=track_id,
    )
    return AdminTrackResponse.model_validate(track)


@router.post(
    "/tracks/{track_id}/playback-health/full-restore",
    response_model=AdminTrackResponse,
    summary=(
        "[Admin] Clear suppression window and playback diagnostic fields"
    ),
)
@limiter.limit("60/minute")
async def admin_full_restore_track_playback_health(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> AdminTrackResponse:
    service = AdminService(session)
    track = await service.full_restore_track_playback_health(track_id)
    if track is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    logger.info(
        "admin_playback_full_restore",
        track_id=track_id,
    )
    return AdminTrackResponse.model_validate(track)


@router.get(
    "/tracks/deleted",
    response_model=AdminTrackListResponse,
    summary="[Admin] List soft-deleted tracks (any reason)",
)
@limiter.limit("60/minute")
async def admin_list_deleted_tracks(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    search: str | None = Query(None, max_length=128),
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> AdminTrackListResponse:
    service = AdminService(session)
    tracks, total = await service.list_deleted_tracks(
        page=page, size=size, search=search
    )
    return AdminTrackListResponse(
        items=await _admin_track_responses(service, tracks),
        total=total,
        page=page,
        size=size,
    )


@router.delete(
    "/tracks/{track_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary=(
        "[Admin] Soft-delete a track (restorable in /admin/tracks/"
        "deleted, hard-purged after grace by daily cron)"
    ),
)
@limiter.limit("30/minute")
async def admin_delete_track(
    request: Request,
    track_id: int,
    reason: str = Query(
        "admin",
        max_length=32,
        description="Soft-delete reason; allowed values from PrivateCore",
    ),
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin_session),
) -> None:
    from app.services.track_lifecycle_adapter import (
        valid_track_delete_reasons,
    )

    if reason not in valid_track_delete_reasons():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported deletion reason",
        )
    service = AdminService(session)
    ok = await service.delete_track(track_id, actor_id=admin.id, reason=reason)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    logger.info(
        "admin_track_soft_deleted",
        track_id=track_id,
        reason=reason,
        actor_id=admin.id,
    )


@router.post(
    "/tracks/{track_id}/restore",
    response_model=AdminTrackResponse,
    summary="[Admin] Restore a soft-deleted track",
)
@limiter.limit("30/minute")
async def admin_restore_track(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin_session),
) -> AdminTrackResponse:
    service = AdminService(session)
    track = await service.restore_track(track_id)
    if track is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not in trash",
        )
    logger.info(
        "admin_track_restored",
        track_id=track_id,
        actor_id=admin.id,
    )
    return AdminTrackResponse.model_validate(track)


@router.delete(
    "/tracks/{track_id}/forever",
    status_code=status.HTTP_204_NO_CONTENT,
    summary=(
        "[Admin] Hard-delete a track immediately (irreversible). "
        "Requires step-up confirmation in the UI."
    ),
)
@limiter.limit("10/minute")
async def admin_hard_delete_track(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin_session),
) -> None:
    service = AdminService(session)
    ok = await service.hard_delete_track_now(track_id, actor_id=admin.id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    logger.info(
        "admin_track_hard_deleted",
        track_id=track_id,
        actor_id=admin.id,
    )


@router.patch(
    "/tracks/{track_id}/visibility",
    response_model=AdminTrackResponse,
    summary="[Admin] Toggle track active/hidden status",
)
@limiter.limit("60/minute")
async def admin_toggle_track_active(
    request: Request,
    track_id: int,
    is_active: bool = Query(...),
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> AdminTrackResponse:
    service = AdminService(session)
    track = await service.set_track_visibility(track_id, is_active)
    if track is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    logger.info(
        "admin_track_visibility_changed",
        track_id=track_id,
        is_active=is_active,
    )
    return AdminTrackResponse.model_validate(track)


@router.patch(
    "/tracks/{track_id}",
    response_model=AdminTrackResponse,
    summary="[Admin] Update track metadata",
)
@limiter.limit("60/minute")
async def admin_update_track(
    request: Request,
    track_id: int,
    data: TrackUpdateRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> AdminTrackResponse:
    fields = data.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    service = AdminService(session)
    track = await service.update_track(track_id, **fields)
    if track is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    logger.info(
        "admin_track_metadata_updated",
        track_id=track_id,
        fields=list(fields.keys()),
    )
    return AdminTrackResponse.model_validate(track)


@router.post(
    "/tracks/{track_id}/cover",
    response_model=AdminTrackResponse,
    summary="[Admin] Upload track cover image",
)
@limiter.limit("30/minute")
async def admin_upload_track_cover(
    request: Request,
    track_id: int,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin_session),
) -> AdminTrackResponse:
    mime = (file.content_type or "").split(";")[0].strip().lower()
    if mime not in _ALLOWED_COVER_CT:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Cover must be JPEG, PNG, or WebP",
        )
    data = await file.read()
    if len(data) > _MAX_COVER_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Cover exceeds 5 MB limit",
        )
    service = AdminService(session)
    track = await service.upload_track_cover(
        track_id,
        data=data,
        content_type=mime,
        admin_user_id=admin.id,
    )
    if track is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    logger.info("admin_track_cover_uploaded", track_id=track_id)
    return AdminTrackResponse.model_validate(track)


@router.patch(
    "/tracks/{track_id}/genre",
    response_model=AdminTrackResponse,
    summary="[Admin] Quickly update track genre",
)
@limiter.limit("60/minute")
async def admin_update_track_genre(
    request: Request,
    track_id: int,
    data: AdminTrackGenrePatchRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> AdminTrackResponse:
    service = AdminService(session)
    track = await service.update_track(track_id, genre=data.genre)
    if track is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    logger.info(
        "admin_track_genre_updated",
        track_id=track_id,
        genre=data.genre,
    )
    return AdminTrackResponse.model_validate(track)


@router.post(
    "/tracks/transcode/{track_id}",
    summary="[Admin] Transcode a single track to HLS",
)
@limiter.limit("10/minute")
async def admin_transcode_track(
    request: Request,
    track_id: int,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> dict:
    service = AdminService(session)
    track = await service.get_track(track_id)
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        )
    if not track.file_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Track has no audio file to transcode",
        )
    background_tasks.add_task(transcode_hls_only, track_id, track.file_key)
    logger.info("admin_transcode_queued", track_id=track_id)
    return {"queued": True, "track_id": track_id}


@router.post(
    "/tracks/transcode/batch",
    summary=(
        "[Admin] Transcode all tracks without HLS to " "adaptive bitrate"
    ),
)
@limiter.limit("2/minute")
async def admin_transcode_batch(
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> dict:
    from app.repositories.track import TrackRepository

    tracks = await TrackRepository(session).list_internal_pending_hls()
    for track in tracks:
        if track.file_key is None:
            continue
        background_tasks.add_task(
            transcode_hls_only,
            track.id,
            track.file_key,
        )
    logger.info(
        "admin_transcode_batch_queued",
        count=len(tracks),
    )
    return {"queued": len(tracks)}


@router.post(
    "/tracks/context/batch-prompt",
    response_model=BatchPromptResponse,
    summary="[Admin] Generate batch prompt for selected tracks",
)
@limiter.limit("30/minute")
async def admin_batch_prompt(
    request: Request,
    data: BatchPromptRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> BatchPromptResponse:
    svc = AdminTrackContextService(session)
    prompt, count = await svc.batch_prompt(data.track_ids)
    logger.info("admin_batch_prompt_generated", track_count=count)
    return BatchPromptResponse(prompt=prompt, track_count=count)


@router.post(
    "/tracks/context/batch-import",
    response_model=BatchImportResponse,
    summary="[Admin] Import AI JSON response into track contexts",
)
@limiter.limit("10/minute")
async def admin_batch_import(
    request: Request,
    data: BatchImportRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> BatchImportResponse:
    svc = AdminTrackContextService(session)
    imported, errors = await svc.batch_import(data.raw_response)
    logger.info(
        "admin_batch_import_done",
        imported=imported,
        error_count=len(errors),
    )
    return BatchImportResponse(imported=imported, errors=errors)


@router.post(
    "/tracks/lyrics/batch-prompt",
    response_model=LyricsBatchPromptResponse,
    summary="[Admin] Generate batch prompt for lyrics import",
)
@limiter.limit("20/minute")
async def admin_batch_lyrics_prompt(
    request: Request,
    data: LyricsBatchPromptRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> LyricsBatchPromptResponse:
    svc = AdminLyricsImportService(session)
    if data.track_ids:
        prompt, count = await svc.build_prompt_for_tracks(data.track_ids)
    else:
        prompt, count = await svc.build_prompt_for_filtered_tracks(
            search=data.search,
            only_without_lyrics=data.only_without_lyrics,
            limit=data.limit,
        )
    logger.info("admin_lyrics_batch_prompt_generated", track_count=count)
    return LyricsBatchPromptResponse(prompt=prompt, track_count=count)


@router.post(
    "/tracks/lyrics/batch-import",
    response_model=LyricsBatchImportResponse,
    summary="[Admin] Import AI response into track lyrics",
)
@limiter.limit("10/minute")
async def admin_batch_lyrics_import(
    request: Request,
    data: LyricsBatchImportRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> LyricsBatchImportResponse:
    svc = AdminLyricsImportService(session)
    imported, errors = await svc.import_ai_response(
        raw_response=data.raw_response,
        skip_existing=data.skip_existing,
    )
    logger.info(
        "admin_lyrics_batch_import_done",
        imported=imported,
        error_count=len(errors),
        skip_existing=data.skip_existing,
    )
    return LyricsBatchImportResponse(imported=imported, errors=errors)


@router.post(
    "/tracks/genre-mood/batch-prompt",
    response_model=GenreMoodBatchPromptResponse,
    summary=(
        "[Admin] Batch prompt for genre/mood from lyrics excerpt + metadata"
    ),
)
@limiter.limit("20/minute")
async def admin_genre_mood_batch_prompt(
    request: Request,
    data: GenreMoodBatchPromptRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> GenreMoodBatchPromptResponse:
    svc = AdminTrackGenreMoodImportService(session)
    if data.track_ids:
        prompt, count = await svc.build_prompt_for_tracks(data.track_ids)
    else:
        prompt, count = await svc.build_prompt_for_filtered(
            search=data.search,
            only_without_genre=data.only_without_genre,
            limit=data.limit,
        )
    logger.info("admin_genre_mood_batch_prompt", track_count=count)
    return GenreMoodBatchPromptResponse(prompt=prompt, track_count=count)


@router.post(
    "/tracks/genre-mood/batch-import",
    response_model=GenreMoodBatchImportResponse,
    summary="[Admin] Import AI JSON into track.genre and mood tags",
)
@limiter.limit("10/minute")
async def admin_genre_mood_batch_import(
    request: Request,
    data: GenreMoodBatchImportRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> GenreMoodBatchImportResponse:
    svc = AdminTrackGenreMoodImportService(session)
    imported, errors = await svc.import_ai_response(
        raw_response=data.raw_response,
        overwrite_genre=data.overwrite_genre,
    )
    logger.info(
        "admin_genre_mood_batch_import",
        imported=imported,
        error_count=len(errors),
    )
    return GenreMoodBatchImportResponse(
        imported=imported,
        errors=errors,
    )


@router.get(
    "/tracks/{track_id}/context",
    response_model=TrackContextResponse,
    summary="[Admin] Get current track context",
)
@limiter.limit("120/minute")
async def admin_get_track_context(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> TrackContextResponse:
    svc = AdminTrackContextService(session)
    row = await svc.get_context(track_id)
    if row is None:
        return TrackContextResponse(
            track_id=track_id,
            content=None,
            status="pending",
            fetched_at=None,
        )
    return TrackContextResponse.model_validate(row)


@router.patch(
    "/tracks/{track_id}/context",
    response_model=TrackContextResponse,
    summary="[Admin] Manually set track context",
)
@limiter.limit("60/minute")
async def admin_set_track_context(
    request: Request,
    track_id: int,
    data: TrackContextUpdateRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> TrackContextResponse:
    svc = AdminTrackContextService(session)
    try:
        row = await svc.set_context(track_id, data.content)
    except TrackNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        ) from None
    logger.info("admin_track_context_set", track_id=track_id)
    return TrackContextResponse.model_validate(row)


@router.delete(
    "/tracks/{track_id}/context",
    response_model=TrackContextResponse,
    summary="[Admin] Clear track context",
)
@limiter.limit("60/minute")
async def admin_clear_track_context(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> TrackContextResponse:
    svc = AdminTrackContextService(session)
    try:
        row = await svc.clear_context(track_id)
    except TrackNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        ) from None
    logger.info("admin_track_context_cleared", track_id=track_id)
    return TrackContextResponse.model_validate(row)


@router.get(
    "/tracks/{track_id}/prompt",
    response_model=SinglePromptResponse,
    summary="[Admin] Generate copy-ready prompt for one track",
)
@limiter.limit("60/minute")
async def admin_get_track_prompt(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> SinglePromptResponse:
    svc = AdminTrackContextService(session)
    try:
        prompt, lang = await svc.single_prompt(track_id)
    except TrackNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Track not found",
        ) from None
    return SinglePromptResponse(prompt=prompt, language=lang)


@router.get(
    "/tracks/{track_id}/upload-meta",
    summary="[Admin] Get upload metadata for a track",
)
@limiter.limit("60/minute")
async def admin_get_upload_meta(
    request: Request,
    track_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> dict:
    from app.repositories.track_upload_meta import (
        TrackUploadMetaRepository,
    )

    meta = await TrackUploadMetaRepository(session).get_by_track_id(track_id)
    if not meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload meta not found",
        )
    return {
        "track_id": meta.track_id,
        "upload_ip": meta.upload_ip,
        "upload_user_agent": meta.upload_user_agent,
        "upload_terms_accepted": (meta.upload_terms_accepted),
        "upload_terms_version": meta.upload_terms_version,
        "upload_telegram_data": meta.upload_telegram_data,
        "created_at": str(meta.created_at),
    }
