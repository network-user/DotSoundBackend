import asyncio
import io

import structlog
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import Response
from PIL import Image, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import s3
from app.core.rate_limit import limiter
from app.dependencies import get_db, get_optional_user
from app.models.user import User
from app.schemas.track import TrackListResponse
from app.services.track_response_build import dedupe_and_build_track_list
from app.services.track_service import TrackService

_COVER_RENDER_WIDTHS = frozenset({120, 240, 480})
_COVER_RENDER_QUALITY = 80

router = APIRouter()
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@router.get(
    "/",
    response_model=TrackListResponse,
)
@limiter.limit("200/minute")
async def list_tracks(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None),
    genre: str | None = Query(None),
    playable: bool = Query(False),
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> TrackListResponse:
    service = TrackService(session)
    if q or genre:
        effective_query = q or genre or ""
        structlog.contextvars.bind_contextvars(search_query=effective_query)
        tracks, total = await service.search(
            effective_query,
            page=page,
            size=size,
            playable_only=playable,
            genre_filter=genre,
        )
    else:
        tracks, total = await service.list_tracks(
            page=page,
            size=size,
            playable_only=playable,
        )
    viewer_id = current_user.id if current_user else None
    items = await dedupe_and_build_track_list(
        session, tracks, viewer_id=viewer_id
    )
    return TrackListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
    )


def _resize_to_webp(data: bytes, width: int) -> bytes:
    img: Image.Image = Image.open(io.BytesIO(data))
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
    else:
        img = img.convert("RGB")
    src_w, src_h = img.size
    if src_w > width:
        ratio = width / src_w
        new_h = max(1, int(src_h * ratio))
        img = img.resize((width, new_h), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(
        buf,
        format="WEBP",
        quality=_COVER_RENDER_QUALITY,
        method=4,
    )
    return buf.getvalue()


@router.get("/cover_proxy")
@limiter.limit("600/minute")
async def cover_proxy(
    request: Request,
    key: str = Query(...),
    w: int | None = Query(None),
) -> Response:
    _ALLOWED_PREFIXES = (
        "covers/",
        "image-blobs/",
        "playlist-covers/",
        "avatars/",
        "artist-avatars/",
        "artists/",
        "chat_photos/",
        "voice/",
    )
    if (
        ".." in key
        or key.startswith("/")
        or not key.startswith(_ALLOWED_PREFIXES)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid key",
        )
    if w is not None and w not in _COVER_RENDER_WIDTHS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported width",
        )
    try:
        data = await s3.download_object(key)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cover not found",
        ) from exc

    if w is None or key.endswith(".ogg"):
        content_type = "image/png"
        if key.endswith(".jpg") or key.endswith(".jpeg"):
            content_type = "image/jpeg"
        elif key.endswith(".webp"):
            content_type = "image/webp"
        elif key.endswith(".ogg"):
            content_type = "audio/ogg"
        return Response(
            content=data,
            media_type=content_type,
            headers={"Cache-Control": "public, max-age=3600"},
        )

    try:
        resized = await asyncio.to_thread(_resize_to_webp, data, w)
    except UnidentifiedImageError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported image",
        ) from exc
    return Response(
        content=resized,
        media_type="image/webp",
        headers={
            "Cache-Control": "public, max-age=86400, immutable",
        },
    )


@router.get(
    "/genres",
    response_model=list[str],
    summary="Get a list of unique track genres currently in the database",
)
@limiter.limit("60/minute")
async def get_genres(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> list[str]:
    service = TrackService(session)
    return await service.get_genres()
