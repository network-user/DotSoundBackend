"""Endpoints for the user's own artist profile (``/artists/me``).

The artist ``name`` is intentionally read-only here -- it is kept in
sync with ``user.display_name`` by ``UserService.update_profile``.
This module manages the strictly artist-only fields (bio, avatar,
country, birthplace, birth_date, website_url) and exposes a small
``ensure`` endpoint so the client can pre-create the artist row from
the dedicated edit screen instead of having to start a track upload.
"""

import structlog
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import s3
from app.core.rate_limit import limiter
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.own_artist import (
    OwnArtistEnsureResponse,
    OwnArtistFields,
    OwnArtistStatusResponse,
    OwnArtistUpdateRequest,
)
from app.services.artist_service import ArtistService

router = APIRouter(prefix="/artists", tags=["artists-me"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_ALLOWED_AVATAR_MIMES = frozenset(
    {"image/jpeg", "image/png", "image/webp"}
)
_MAX_AVATAR_BYTES = 5 * 1024 * 1024


def _to_fields(artist) -> OwnArtistFields:
    return OwnArtistFields.model_validate(artist)


@router.get(
    "/me",
    response_model=OwnArtistStatusResponse,
)
@limiter.limit("60/minute")
async def get_my_artist(
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OwnArtistStatusResponse:
    svc = ArtistService(session)
    owned = await svc.get_owned_for_user(current_user.id)
    return OwnArtistStatusResponse(
        has_artist=owned is not None,
        display_name=current_user.display_name,
        artist=_to_fields(owned) if owned else None,
    )


@router.post(
    "/me/ensure",
    response_model=OwnArtistEnsureResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("10/minute")
async def ensure_my_artist(
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OwnArtistEnsureResponse:
    display = (current_user.display_name or "").strip()
    if not display:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "display_name is empty. Set it in your profile "
                "before creating an artist."
            ),
        )
    svc = ArtistService(session)
    artist = await svc.ensure_owned_artist_for_user(
        user_id=current_user.id,
        preferred_name=display,
    )
    return OwnArtistEnsureResponse(artist=_to_fields(artist))


@router.patch(
    "/me",
    response_model=OwnArtistFields,
)
@limiter.limit("60/minute")
async def update_my_artist(
    request: Request,
    body: OwnArtistUpdateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OwnArtistFields:
    raw = body.model_dump(exclude_unset=True)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    svc = ArtistService(session)
    patched = await svc.update_owned_profile(
        user_id=current_user.id,
        **{
            k: (raw[k] if k in raw else ...)
            for k in (
                "bio",
                "country",
                "birth_date",
                "birthplace",
                "website_url",
            )
        },
    )
    return _to_fields(patched)


@router.delete(
    "/me/avatar",
    response_model=OwnArtistFields,
)
@limiter.limit("12/minute")
async def remove_my_artist_avatar(
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OwnArtistFields:
    """Detach the avatar from the owned artist.

    The underlying S3/CAS object is left to the existing image-blob
    garbage collector -- naive deletion here would be wrong because
    image keys are content-addressed and may be referenced by other
    rows.
    """
    svc = ArtistService(session)
    patched = await svc.update_owned_profile(
        user_id=current_user.id,
        image_key=None,
    )
    return _to_fields(patched)


@router.post(
    "/me/avatar",
    response_model=OwnArtistFields,
)
@limiter.limit("12/minute")
async def upload_my_artist_avatar(
    request: Request,
    avatar: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OwnArtistFields:
    mime = (avatar.content_type or "").lower()
    if mime not in _ALLOWED_AVATAR_MIMES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported image format: {mime}",
        )
    data = await avatar.read()
    if len(data) > _MAX_AVATAR_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Avatar exceeds 5 MB limit",
        )

    from app.services.file_validator import validate_image_async

    await validate_image_async(data, avatar.filename)

    img_key, _, _, _ = await s3.upload_image(
        data,
        prefix="artist-avatars",
        max_size=None,
        user_id=current_user.id,
        session=session,
    )

    svc = ArtistService(session)
    patched = await svc.update_owned_profile(
        user_id=current_user.id,
        image_key=img_key,
    )
    return _to_fields(patched)
