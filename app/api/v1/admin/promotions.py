"""Admin endpoints for editorial promotions (boost campaigns)."""

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
from app.dependencies import get_db, require_capability
from app.models.user import User
from app.repositories.admin_action_log import AdminActionLogRepository
from app.schemas.promotion import (
    PromotionAdminDetail,
    PromotionAdminListResponse,
    PromotionCreateRequest,
    PromotionPatchRequest,
    PromotionStatsResponse,
)
from app.services.promotion_service import (
    UNSET,
    PromotionService,
    PromotionValidationError,
)

router = APIRouter(prefix="/promotions", tags=["admin-promotions"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get(
    "",
    response_model=PromotionAdminListResponse,
    summary="[Admin] List promotions",
)
@limiter.limit("60/minute")
async def list_promotions(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    entity_type: str | None = Query(None, max_length=16),
    is_active: bool | None = Query(None),
    surface: str | None = Query(None, max_length=16),
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_capability("promotions.manage")),
) -> PromotionAdminListResponse:
    svc = PromotionService(session)
    items, total = await svc.list_for_admin(
        page=page,
        size=size,
        entity_type=entity_type,
        is_active=is_active,
        surface=surface,
    )
    return PromotionAdminListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
    )


@router.get(
    "/{promotion_id}",
    response_model=PromotionAdminDetail,
    summary="[Admin] Get promotion",
)
@limiter.limit("120/minute")
async def get_promotion(
    request: Request,
    promotion_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_capability("promotions.manage")),
) -> PromotionAdminDetail:
    svc = PromotionService(session)
    detail = await svc.get_for_admin(promotion_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Promotion not found",
        )
    return detail


@router.post(
    "",
    response_model=PromotionAdminDetail,
    status_code=status.HTTP_201_CREATED,
    summary="[Admin] Create promotion",
)
@limiter.limit("30/minute")
async def create_promotion(
    request: Request,
    body: PromotionCreateRequest,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_capability("promotions.manage")),
) -> PromotionAdminDetail:
    svc = PromotionService(session)
    try:
        promotion = await svc.create(
            entity_type=body.entity_type,
            entity_id=body.entity_id,
            surfaces=list(body.surfaces),
            priority=body.priority,
            starts_at=body.starts_at,
            ends_at=body.ends_at,
            is_active=body.is_active,
            title_override=body.title_override,
            subtitle_override=body.subtitle_override,
            cta_label_override=body.cta_label_override,
            cover_url_override=body.cover_url_override,
            admin_user_id=admin.id,
        )
    except PromotionValidationError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from err

    await AdminActionLogRepository(session).write(
        user_id=admin.id,
        action="promotions.create",
        target_type="promotion",
        target_id=str(promotion.id),
        ip=_client_ip(request),
        meta={
            "entity_type": body.entity_type,
            "entity_id": body.entity_id,
            "surfaces": sorted(body.surfaces),
            "priority": body.priority,
        },
    )
    await session.commit()
    detail = await svc.get_for_admin(promotion.id)
    assert detail is not None
    return detail


@router.patch(
    "/{promotion_id}",
    response_model=PromotionAdminDetail,
    summary="[Admin] Update promotion",
)
@limiter.limit("60/minute")
async def patch_promotion(
    request: Request,
    promotion_id: int,
    body: PromotionPatchRequest,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_capability("promotions.manage")),
) -> PromotionAdminDetail:
    svc = PromotionService(session)
    promotion = await svc.get_raw(promotion_id)
    if promotion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Promotion not found",
        )
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    try:
        await svc.update(
            promotion,
            surfaces=fields.get("surfaces"),
            priority=fields.get("priority"),
            starts_at=fields.get("starts_at", UNSET),
            ends_at=fields.get("ends_at", UNSET),
            is_active=fields.get("is_active"),
            title_override=fields.get("title_override", UNSET),
            subtitle_override=fields.get("subtitle_override", UNSET),
            cta_label_override=fields.get("cta_label_override", UNSET),
            cover_url_override=fields.get("cover_url_override", UNSET),
            admin_user_id=admin.id,
        )
    except PromotionValidationError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from err

    await AdminActionLogRepository(session).write(
        user_id=admin.id,
        action="promotions.update",
        target_type="promotion",
        target_id=str(promotion_id),
        ip=_client_ip(request),
        meta={"fields": sorted(fields.keys())},
    )
    await session.commit()
    detail = await svc.get_for_admin(promotion_id)
    assert detail is not None
    return detail


@router.delete(
    "/{promotion_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="[Admin] Delete promotion",
)
@limiter.limit("30/minute")
async def delete_promotion(
    request: Request,
    promotion_id: int,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_capability("promotions.manage")),
) -> None:
    svc = PromotionService(session)
    promotion = await svc.get_raw(promotion_id)
    if promotion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Promotion not found",
        )
    await svc.delete(promotion)
    await AdminActionLogRepository(session).write(
        user_id=admin.id,
        action="promotions.delete",
        target_type="promotion",
        target_id=str(promotion_id),
        ip=_client_ip(request),
    )
    await session.commit()


@router.get(
    "/{promotion_id}/stats",
    response_model=PromotionStatsResponse,
    summary="[Admin] Promotion stats (impressions/clicks/plays)",
)
@limiter.limit("60/minute")
async def get_promotion_stats(
    request: Request,
    promotion_id: int,
    period_days: int = Query(30, ge=1, le=365),
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_capability("promotions.manage")),
) -> PromotionStatsResponse:
    svc = PromotionService(session)
    stats = await svc.get_stats(promotion_id, period_days=period_days)
    if stats is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Promotion not found",
        )
    return stats
