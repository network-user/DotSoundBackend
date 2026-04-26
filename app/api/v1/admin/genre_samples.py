from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, require_capability
from app.models.user import User
from app.schemas.genre_samples import (
    AdminGenreSampleCreateRequest,
    AdminGenreSampleItem,
    AdminGenreSampleListResponse,
)
from app.services.genre_samples_service import GenreSamplesService

router = APIRouter(prefix="/genre-samples", tags=["admin", "genre-samples"])


@router.get(
    "",
    response_model=AdminGenreSampleListResponse,
    summary="List curated genre samples for a genre",
)
async def list_genre_samples(
    genre: str = Query(..., min_length=1, max_length=64),
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_capability("recsys.genre_samples.manage")),
) -> AdminGenreSampleListResponse:
    _ = _admin
    svc = GenreSamplesService(session)
    rows = await svc.list_curated(genre)
    return AdminGenreSampleListResponse(
        items=[AdminGenreSampleItem.model_validate(r) for r in rows],
    )


@router.post(
    "/{genre}",
    response_model=AdminGenreSampleItem,
    status_code=status.HTTP_201_CREATED,
    summary="Add a track to the curated list for a genre",
)
async def add_genre_sample(
    genre: str,
    body: AdminGenreSampleCreateRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_capability("recsys.genre_samples.manage")),
) -> AdminGenreSampleItem:
    _ = _admin
    svc = GenreSamplesService(session)
    try:
        row = await svc.add_curated(
            genre=genre,
            track_id=body.track_id,
            position=body.position,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate genre sample",
        ) from exc
    await session.refresh(row)
    return AdminGenreSampleItem.model_validate(row)


@router.delete(
    "/{sample_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a curated genre sample by row id",
)
async def remove_genre_sample(
    sample_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_capability("recsys.genre_samples.manage")),
) -> Response:
    _ = _admin
    svc = GenreSamplesService(session)
    ok = await svc.remove_curated(sample_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )
    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )
