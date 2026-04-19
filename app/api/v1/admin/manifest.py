"""Admin manifest endpoint.

Non-admins receive 404 instead of 403 so that the existence of
the feature surface is not disclosed.
"""

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

from app.dependencies import (
    get_current_user,
    get_db,
)
from app.models.user import User
from app.services.admin_manifest_service import (
    build_manifest,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter()


@router.get("/manifest")
async def get_admin_manifest(
    request: Request,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    locale = (
        request.query_params.get("locale")
        or getattr(user, "locale", None)
        or "ru"
    )
    manifest = await build_manifest(session, user, locale=locale)
    logger.info(
        "admin_manifest_built",
        user_id=user.id,
        caps=len(manifest["capabilities"]),
    )
    return manifest
