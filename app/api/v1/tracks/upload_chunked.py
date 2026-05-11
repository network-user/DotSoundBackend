"""Chunked, resumable, cancellable v2 upload API.

Endpoints (all under ``/api/v1/tracks/upload``):

* ``POST /init``                   -- open a session, returns ``upload_id`` + plan
* ``PUT  /{upload_id}/chunk/{idx}``-- upload one part; idempotent per ``idx``
* ``GET  /{upload_id}``            -- session status (for resume)
* ``POST /{upload_id}/complete``   -- finalize: assemble + start transcoding
* ``DELETE /{upload_id}``          -- cancel & abort multipart upload
* ``POST /check-duplicate``        -- check a hash against current user's library

Route handlers stay thin: validation + delegation to
``ChunkedUploadService`` / ``DedupeService``.
"""

import structlog
from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Request,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.upload_chunked import (
    DuplicateCheckRequest,
    DuplicateCheckResponse,
    UploadCompleteResponse,
    UploadInitRequest,
    UploadInitResponse,
    UploadStatusResponse,
)
from app.services.chunked_upload_service import ChunkedUploadService
from app.services.dedupe_service import DedupeService

router = APIRouter()
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_CURRENT_UPLOAD_TERMS_VERSION = "2026-04-15"


@router.post(
    "/upload/init",
    response_model=UploadInitResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("20/minute")
async def init_chunked_upload(
    request: Request,
    body: UploadInitRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UploadInitResponse:
    if not body.upload_terms_accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload terms must be accepted",
        )
    effective_artist = body.artist
    if body.use_profile_artist:
        effective_artist = current_user.display_name
        if not effective_artist:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Display name is required for profile artist mode",
            )

    svc = ChunkedUploadService(session)
    record = await svc.init(
        user_id=current_user.id,
        filename=body.filename,
        mime=body.mime,
        total_size=body.total_size,
        audio_hash=body.audio_hash,
        meta={
            "title": body.title,
            "artist": effective_artist,
            "use_profile_artist": body.use_profile_artist,
            "genre": body.genre,
            "is_public": body.is_public,
            "upload_terms_version": _CURRENT_UPLOAD_TERMS_VERSION,
        },
    )

    return UploadInitResponse(
        upload_id=record.upload_id,
        chunk_size=record.chunk_size,
        expected_chunks=record.expected_chunks,
        expires_at=record.expires_at,
        completed_chunks=list(record.completed_chunks or []),
    )


@router.put(
    "/upload/{upload_id}/chunk/{chunk_index}",
    response_model=UploadStatusResponse,
)
@limiter.limit("600/minute")
async def upload_chunk(
    request: Request,
    upload_id: str = Path(..., min_length=36, max_length=36),
    chunk_index: int = Path(..., ge=0),
    chunk: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UploadStatusResponse:
    data = await chunk.read()
    svc = ChunkedUploadService(session)
    record = await svc.upload_chunk(
        upload_id=upload_id,
        user_id=current_user.id,
        chunk_index=chunk_index,
        data=data,
    )
    return UploadStatusResponse(
        upload_id=record.upload_id,
        status=record.status,
        completed_chunks=list(record.completed_chunks or []),
        expected_chunks=record.expected_chunks,
        expires_at=record.expires_at,
        track_id=record.track_id,
    )


@router.get(
    "/upload/{upload_id}",
    response_model=UploadStatusResponse,
)
@limiter.limit("120/minute")
async def get_upload_status(
    request: Request,
    upload_id: str = Path(..., min_length=36, max_length=36),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UploadStatusResponse:
    svc = ChunkedUploadService(session)
    record = await svc.status(
        upload_id=upload_id, user_id=current_user.id
    )
    return UploadStatusResponse(
        upload_id=record.upload_id,
        status=record.status,
        completed_chunks=list(record.completed_chunks or []),
        expected_chunks=record.expected_chunks,
        expires_at=record.expires_at,
        track_id=record.track_id,
    )


@router.post(
    "/upload/{upload_id}/complete",
    response_model=UploadCompleteResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("30/minute")
async def complete_chunked_upload(
    request: Request,
    upload_id: str = Path(..., min_length=36, max_length=36),
    cover: UploadFile | None = File(None),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UploadCompleteResponse:
    cover_key: str | None = None
    if cover and cover.filename:
        from app.services.upload_service import UploadService

        upload_svc = UploadService(session)
        cover_key = await upload_svc._upload_cover(
            cover, current_user.id
        )

    svc = ChunkedUploadService(session)
    track = await svc.complete(
        upload_id=upload_id,
        user_id=current_user.id,
        cover_key=cover_key,
    )

    from app.models.upload_meta import TrackUploadMeta

    meta = TrackUploadMeta(
        track_id=track.id,
        upload_ip=(
            request.client.host if request.client else None
        ),
        upload_user_agent=request.headers.get("user-agent"),
        upload_terms_accepted=True,
        upload_terms_version=_CURRENT_UPLOAD_TERMS_VERSION,
    )
    session.add(meta)
    await session.flush()

    return UploadCompleteResponse(
        track_id=track.id, upload_id=upload_id
    )


@router.delete(
    "/upload/{upload_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@limiter.limit("30/minute")
async def cancel_chunked_upload(
    request: Request,
    upload_id: str = Path(..., min_length=36, max_length=36),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    svc = ChunkedUploadService(session)
    await svc.cancel(upload_id=upload_id, user_id=current_user.id)


@router.post(
    "/check-duplicate",
    response_model=DuplicateCheckResponse,
)
@limiter.limit("60/minute")
async def check_duplicate(
    request: Request,
    body: DuplicateCheckRequest = Body(...),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DuplicateCheckResponse:
    svc = DedupeService(session)
    existing = await svc.find_for_user(
        user_id=current_user.id, audio_hash=body.audio_hash
    )
    if existing is None:
        return DuplicateCheckResponse(exists=False)
    return DuplicateCheckResponse(
        exists=True,
        track_id=existing.id,
        title=existing.title,
        uploaded_at=existing.created_at,
    )
