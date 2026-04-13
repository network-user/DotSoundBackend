from __future__ import annotations

import structlog
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.rate_limit import limiter
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.account import (
    LinkConflictResponse,
    LinkEmailRequest,
    LinkEmailVerifyRequest,
    LinkStatusResponse,
    LinkTelegramRequest,
    MergeRequest,
)
from app.services.account_linking_service import (
    LinkConflict,
    LinkingError,
    generate_link_telegram_code,
    merge_accounts,
    request_link_email,
    verify_link_email,
    verify_link_telegram,
)

router = APIRouter(
    prefix="/account", tags=["account"]
)

logger: structlog.stdlib.BoundLogger = (
    structlog.get_logger(__name__)
)


@router.get(
    "/link-status",
    response_model=LinkStatusResponse,
)
async def link_status(
    user: User = Depends(get_current_user),
) -> LinkStatusResponse:
    return LinkStatusResponse(
        telegram_linked=(
            user.telegram_id is not None
        ),
        email_linked=user.email is not None,
        email=user.email,
        telegram_username=user.username,
    )


@router.post("/link/email")
@limiter.limit("5/15minutes")
async def link_email(
    request: Request,
    body: LinkEmailRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    try:
        await request_link_email(
            user, body.email
        )
    except LinkingError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=str(exc),
        )
    return {"status": "verification_email_sent"}


@router.post("/link/email/verify")
async def link_email_verify(
    body: LinkEmailVerifyRequest,
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    try:
        await verify_link_email(
            body.token, session
        )
    except LinkConflict as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "email_already_linked",
                "message": str(exc),
                "has_telegram": exc.has_telegram,
                "has_email": exc.has_email,
                "can_merge": exc.can_merge,
            },
        )
    except LinkingError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=str(exc),
        )
    return {"status": "email_linked"}


@router.post("/link/telegram/generate-code")
async def link_telegram_generate_code(
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    code = await generate_link_telegram_code(user)
    return {
        "code": code,
        "bot_username": (
            settings.telegram_bot_username
        ),
        "deep_link": (
            f"https://t.me/"
            f"{settings.telegram_bot_username}"
            f"?start=link_{code}"
        ),
    }


@router.post("/link/telegram")
async def link_telegram(
    request: Request,
    body: LinkTelegramRequest,
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    try:
        await verify_link_telegram(
            body.code, body.telegram_id, session
        )
    except LinkConflict as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": (
                    "telegram_already_linked"
                ),
                "message": str(exc),
                "has_telegram": exc.has_telegram,
                "has_email": exc.has_email,
                "can_merge": exc.can_merge,
            },
        )
    except LinkingError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=str(exc),
        )
    return {"status": "telegram_linked"}


@router.post("/merge")
@limiter.limit("1/day")
async def merge(
    request: Request,
    body: MergeRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    try:
        await merge_accounts(
            body.source_account_token,
            user,
            session,
        )
    except LinkConflict as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "merge_not_possible",
                "message": str(exc),
                "can_merge": exc.can_merge,
            },
        )
    except LinkingError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=str(exc),
        )
    return {"status": "accounts_merged"}
