"""Public endpoints for editorial promotions (hero, section, pin, events)."""

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.dependencies import get_db, get_optional_user
from app.models.user import User
from app.schemas.promotion import (
    PromotionEventAck,
    PromotionEventCreateRequest,
    PromotionListResponse,
)
from app.services.promotion_service import (
    PromotionService,
    PromotionValidationError,
)

router = APIRouter(prefix="/promotions", tags=["promotions"])


@router.get(
    "/hero",
    response_model=PromotionListResponse,
    summary="Active hero promotions",
)
@limiter.limit("120/minute")
async def get_hero_promotions(
    request: Request,
    limit: int = Query(3, ge=1, le=10),
    session: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> PromotionListResponse:
    svc = PromotionService(session)
    items = await svc.get_for_surface(
        "hero",
        user_id=user.id if user else None,
        limit=limit,
    )
    return PromotionListResponse(items=items)


@router.get(
    "/section",
    response_model=PromotionListResponse,
    summary="Active section promotions (carousel below hero)",
)
@limiter.limit("120/minute")
async def get_section_promotions(
    request: Request,
    limit: int = Query(10, ge=1, le=30),
    session: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> PromotionListResponse:
    svc = PromotionService(session)
    items = await svc.get_for_surface(
        "section",
        user_id=user.id if user else None,
        limit=limit,
    )
    return PromotionListResponse(items=items)


@router.get(
    "/search-pin",
    response_model=PromotionListResponse,
    summary="Pinned promotions for search results",
)
@limiter.limit("120/minute")
async def get_search_pin_promotions(
    request: Request,
    query: str | None = Query(None, max_length=128),
    limit: int = Query(3, ge=1, le=10),
    session: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> PromotionListResponse:
    svc = PromotionService(session)
    items = await svc.get_for_surface(
        "search_pin",
        user_id=user.id if user else None,
        limit=limit,
    )
    if query:
        needle = query.strip().lower()
        if needle:
            items = [
                item
                for item in items
                if needle in (item.title or "").lower()
                or needle in (item.subtitle or "").lower()
                or needle in (item.entity.title or "").lower()
            ]
    return PromotionListResponse(items=items)


@router.post(
    "/{promotion_id}/event",
    response_model=PromotionEventAck,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Record impression or click for a promotion",
)
@limiter.limit("300/minute")
async def record_promotion_event(
    request: Request,
    promotion_id: int,
    body: PromotionEventCreateRequest,
    session: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> PromotionEventAck:
    svc = PromotionService(session)
    try:
        ok = await svc.record_event(
            promotion_id=promotion_id,
            event_type=body.event_type,
            surface=body.surface,
            user_id=user.id if user else None,
        )
    except PromotionValidationError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from err
    return PromotionEventAck(ok=ok)
