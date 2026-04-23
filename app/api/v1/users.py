import mimetypes

import structlog
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import s3
from app.core.rate_limit import limiter
from app.dependencies import get_current_user, get_db
from app.models.track import Track
from app.models.user import User
from app.repositories.complaint import (
    ComplaintRepository,
)
from app.schemas.album import AlbumResponse
from app.schemas.complaint import ComplaintResponse
from app.schemas.eq import (
    EqSettingsRequest,
    EqSettingsResponse,
)
from app.schemas.track import TrackListResponse, TrackResponse
from app.schemas.user import (
    AvatarResponse,
    DeleteAccountRequest,
    UserCreate,
    UserResponse,
    UserStatsResponse,
    UserUpdateRequest,
)
from app.services.album_service import AlbumService
from app.services.eq_service import EqService
from app.services.follow_service import FollowService
from app.services.signal_service import (
    SignalService,
)
from app.services.stats_service import StatsService
from app.services.track_service import TrackService
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_ALLOWED_AVATAR_MIMES = frozenset({"image/jpeg", "image/png", "image/webp"})
_MAX_AVATAR_BYTES = 2 * 1024 * 1024


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Register or update a user by Telegram ID",
)
@limiter.limit("60/minute")
async def register_or_update_user(
    request: Request,
    data: UserCreate,
    session: AsyncSession = Depends(get_db),
) -> UserResponse:
    structlog.contextvars.bind_contextvars(telegram_id=data.telegram_id)
    service = UserService(session)
    user, created = await service.register_or_update(data)
    status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    logger.info(
        "user_endpoint_response",
        user_id=user.id,
        created=created,
        status_code=status_code,
    )
    return UserResponse.model_validate(user)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user profile by internal ID",
)
@limiter.limit("120/minute")
async def get_user(
    request: Request,
    user_id: int,
    session: AsyncSession = Depends(get_db),
) -> UserResponse:
    structlog.contextvars.bind_contextvars(user_id=user_id)
    service = UserService(session)
    user = await service.get_by_id(user_id)
    if not user:
        logger.warning("user_not_found_endpoint", user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse.model_validate(user)


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update own display name",
)
@limiter.limit("30/minute")
async def update_me(
    request: Request,
    data: UserUpdateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    structlog.contextvars.bind_contextvars(user_id=current_user.id)
    if not data.display_name and data.locale is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    service = UserService(session)
    user = await service.get_by_id(current_user.id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if data.display_name:
        user = await service.update_display_name(
            current_user.id, data.display_name
        )
    if data.locale is not None and user:
        user.locale = data.locale
        session = service._repo._session
        await session.flush()
        await session.refresh(user)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse.model_validate(user)


@router.delete(
    "/me",
    status_code=status.HTTP_200_OK,
    summary="Request account deletion (soft delete)",
)
@limiter.limit("3/hour")
async def delete_me(
    request: Request,
    data: DeleteAccountRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    service = UserService(session)
    ok = await service.request_deletion(current_user.id, data.confirmation)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid confirmation text",
        )
    return {"status": "deletion_scheduled"}


@router.post(
    "/me/restore",
    response_model=UserResponse,
    summary="Cancel account deletion within grace period",
)
@limiter.limit("5/hour")
async def restore_me(
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    service = UserService(session)
    ok = await service.cancel_deletion(current_user.id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending deletion or grace period expired",
        )
    user = await service.get_by_id(current_user.id)
    return UserResponse.model_validate(user)


@router.post(
    "/me/avatar",
    response_model=AvatarResponse,
    summary="Upload own avatar",
)
@limiter.limit("10/minute")
async def upload_my_avatar(
    request: Request,
    avatar: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AvatarResponse:
    structlog.contextvars.bind_contextvars(user_id=current_user.id)
    mime = avatar.content_type or ""
    if not mime or mime == "application/octet-stream":
        guessed, _ = mimetypes.guess_type(avatar.filename or "")
        mime = guessed or mime
    if mime not in _ALLOWED_AVATAR_MIMES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Avatar must be JPEG, PNG, or WebP",
        )
    data = await avatar.read()
    if len(data) > _MAX_AVATAR_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Avatar exceeds 2 MB limit",
        )
    avatar_key = await s3.upload_avatar(
        data=data, content_type=mime, user_id=current_user.id
    )
    service = UserService(session)
    await service.update_avatar_key(current_user.id, avatar_key)
    avatar_url = await s3.get_presigned_url(avatar_key)
    logger.info(
        "avatar_uploaded",
        user_id=current_user.id,
        avatar_key=avatar_key,
    )
    return AvatarResponse(avatar_url=avatar_url)


@router.get(
    "/{user_id}/avatar",
    response_model=AvatarResponse,
    summary="Get presigned URL for user avatar",
)
@limiter.limit("120/minute")
async def get_avatar(
    request: Request,
    user_id: int,
    session: AsyncSession = Depends(get_db),
) -> AvatarResponse:
    structlog.contextvars.bind_contextvars(user_id=user_id)
    service = UserService(session)
    user = await service.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.avatar_key:
        avatar_url = await s3.get_presigned_url(user.avatar_key)
    else:
        seed = user.avatar_seed or str(user.telegram_id)
        avatar_url = f"https://api.dicebear.com/9.x/identicon/svg?seed={seed}"

    return AvatarResponse(avatar_url=avatar_url)


@router.get(
    "/me/feed",
    response_model=TrackListResponse,
    summary="Get feed of tracks from followed users (auth required)",
)
@limiter.limit("60/minute")
async def get_feed(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TrackListResponse:
    structlog.contextvars.bind_contextvars(user_id=current_user.id)
    service = FollowService(session)
    tracks, total = await service.get_feed(current_user.id, page, size)
    items = [TrackResponse.model_validate(t) for t in tracks]
    return TrackListResponse(items=items, total=total, page=page, size=size)


@router.get(
    "/me/listen-history",
    response_model=TrackListResponse,
    summary=(
        "Tracks the user has listened to "
        "(listen events, newest first)"
    ),
)
@limiter.limit("60/minute")
async def get_my_listen_history(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TrackListResponse:
    structlog.contextvars.bind_contextvars(
        user_id=current_user.id
    )
    signal_svc = SignalService(session)
    events = await signal_svc.get_recent_listens(
        current_user.id, limit=500
    )
    track_ids: list[int] = []
    seen: set[int] = set()
    for ev in events:
        if ev.track_id in seen:
            continue
        seen.add(ev.track_id)
        track_ids.append(ev.track_id)
        if len(track_ids) >= limit:
            break
    if not track_ids:
        return TrackListResponse(
            items=[], total=0, page=1, size=1
        )
    result = await session.execute(
        select(Track).where(
            Track.id.in_(track_ids),
            Track.is_active.is_(True),
        )
    )
    by_id = {t.id: t for t in result.scalars().all()}
    items: list[TrackResponse] = []
    for tid in track_ids:
        t = by_id.get(tid)
        if t:
            items.append(TrackResponse.model_validate(t))
    return TrackListResponse(
        items=items, total=len(items), page=1, size=len(items)
    )


class _MyComplaintsResponse(BaseModel):
    items: list[ComplaintResponse]


@router.get(
    "/me/complaints",
    response_model=_MyComplaintsResponse,
    summary="Complaints submitted by the current user",
)
@limiter.limit("60/minute")
async def get_my_complaints(
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> _MyComplaintsResponse:
    repo = ComplaintRepository(session)
    items = await repo.list_by_user(
        current_user.id, limit=100
    )
    return _MyComplaintsResponse(
        items=[
            ComplaintResponse.model_validate(c)
            for c in items
        ],
    )


@router.get(
    "/me/library",
    response_model=TrackListResponse,
    summary=(
        "Tracks in current user's library "
        "(uploaded by them and/or imported)"
    ),
)
@limiter.limit("60/minute")
async def get_my_library(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    playable_only: bool = Query(False),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TrackListResponse:
    structlog.contextvars.bind_contextvars(user_id=current_user.id)
    service = TrackService(session)
    tracks, total = await service.list_library(
        user_id=current_user.id,
        page=page,
        size=size,
        playable_only=playable_only,
    )
    items = [TrackResponse.model_validate(t) for t in tracks]
    return TrackListResponse(items=items, total=total, page=page, size=size)


@router.get(
    "/{user_id}/tracks",
    response_model=TrackListResponse,
    summary="Get public tracks uploaded by a user",
)
@limiter.limit("120/minute")
async def get_user_tracks(
    request: Request,
    user_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
) -> TrackListResponse:
    structlog.contextvars.bind_contextvars(user_id=user_id)
    service = TrackService(session)
    tracks, total = await service.list_public_by_user(user_id, page, size)
    items = [TrackResponse.model_validate(t) for t in tracks]
    return TrackListResponse(items=items, total=total, page=page, size=size)


@router.get(
    "/{user_id}/albums",
    response_model=list[AlbumResponse],
    summary="Get albums created by a user",
)
@limiter.limit("120/minute")
async def get_user_albums(
    request: Request,
    user_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
) -> list[AlbumResponse]:
    structlog.contextvars.bind_contextvars(user_id=user_id)
    service = AlbumService(session)
    albums, _ = await service.list_by_user(user_id, page, size)
    return [AlbumResponse.model_validate(a) for a in albums]


@router.get(
    "/{user_id}/stats",
    response_model=UserStatsResponse,
    summary="Get author analytics for a user",
)
@limiter.limit("60/minute")
async def get_user_stats(
    request: Request,
    user_id: int,
    session: AsyncSession = Depends(get_db),
) -> UserStatsResponse:
    structlog.contextvars.bind_contextvars(user_id=user_id)
    service = StatsService(session)
    stats = await service.get_author_stats(user_id)
    logger.info(
        "stats_endpoint_response",
        user_id=user_id,
        total_tracks=stats.total_tracks,
        total_plays=stats.total_plays,
    )
    return stats


@router.get(
    "/{user_id}/login-history",
)
@limiter.limit("30/minute")
async def get_login_history(
    request: Request,
    user_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    if current_user.id != user_id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    from sqlalchemy import select

    from app.models.login_history import LoginHistory

    result = await session.execute(
        select(LoginHistory)
        .where(LoginHistory.user_id == user_id)
        .order_by(LoginHistory.created_at.desc())
        .limit(10)
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "ip": r.ip,
            "device": r.device,
            "login_type": r.login_type,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get(
    "/me/eq",
    response_model=EqSettingsResponse,
)
@limiter.limit("60/minute")
async def get_eq_settings(
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EqSettingsResponse:
    service = EqService(session)
    return await service.get_settings(current_user.id)


@router.put(
    "/me/eq",
    response_model=EqSettingsResponse,
)
@limiter.limit("30/minute")
async def save_eq_settings(
    request: Request,
    body: EqSettingsRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EqSettingsResponse:
    service = EqService(session)
    return await service.save_settings(
        current_user.id,
        body.preset,
        body.bands,
    )
