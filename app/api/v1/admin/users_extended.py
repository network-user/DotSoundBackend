"""Extended admin user-management endpoints.

These live alongside ``users.py`` and add the actions the admin
panel needs beyond the basic list/update — ban, role grants and
capability management — all guarded by step-up auth.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import (
    get_db,
    require_admin_session,
    require_capability,
    require_step_up,
)
from app.models.user import User
from app.repositories.admin_capability import (
    AdminCapabilityRepository,
)
from app.repositories.admin_login_attempt import (
    AdminLoginAttemptRepository,
)
from app.repositories.admin_session import (
    AdminSessionRepository,
)
from app.repositories.login_history import (
    LoginHistoryRepository,
)
from app.repositories.user import UserRepository
from app.services.admin_alert_service import (
    dispatch_alert,
)
from app.services.admin_manifest_service import (
    KNOWN_CAPABILITIES,
)
from app.services.admin_service import AdminService

router = APIRouter(prefix="/users-ext", tags=["admin-users"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@router.get("/{user_id}/login-history")
async def login_history(
    user_id: int,
    limit: int = Query(50, ge=1, le=500),
    _admin: User = Depends(require_capability("audit.view")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows = await LoginHistoryRepository(session).list_for_user(
        user_id, limit=limit
    )
    return {
        "items": [
            {
                "id": row.id,
                "ip": row.ip,
                "device": row.device,
                "login_type": row.login_type,
                "created_at": row.created_at,
            }
            for row in rows
        ]
    }


@router.get("/{user_id}/admin-attempts")
async def admin_login_attempts(
    user_id: int,
    limit: int = Query(50, ge=1, le=500),
    _admin: User = Depends(require_capability("security.view")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows = await AdminLoginAttemptRepository(session).list_for_user(
        user_id, limit=limit
    )
    return {
        "items": [
            {
                "id": row.id,
                "ip": row.ip,
                "ua": row.ua,
                "success": row.success,
                "reason": row.reason,
                "created_at": row.created_at,
            }
            for row in rows
        ]
    }


@router.get("/{user_id}/admin-sessions")
async def admin_sessions(
    user_id: int,
    _admin: User = Depends(require_capability("security.view")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows = await AdminSessionRepository(session).list_for_user(
        user_id, limit=100
    )
    return {
        "items": [
            {
                "id": row.id,
                "device_id": row.device_id,
                "ip": row.ip,
                "ua": row.ua,
                "created_at": row.created_at,
                "last_seen_at": row.last_seen_at,
                "expires_at": row.expires_at,
                "revoked_at": row.revoked_at,
            }
            for row in rows
        ]
    }


@router.post("/{user_id}/ban")
async def ban_user(
    user_id: int,
    _admin: User = Depends(require_step_up("users.ban")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    service = AdminService(session)
    user = await service.update_user(
        user_id,
        display_name=None,
        is_active=False,
        is_admin=None,
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found",
        )
    await dispatch_alert(
        event_type="user_banned",
        severity="warning",
        title="User banned",
        details=f"user_id={user_id}",
        user_id=_admin.id,
    )
    return {"id": user.id, "is_active": user.is_active}


@router.post("/{user_id}/unban")
async def unban_user(
    user_id: int,
    _admin: User = Depends(require_step_up("users.unban")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    service = AdminService(session)
    user = await service.update_user(
        user_id,
        display_name=None,
        is_active=True,
        is_admin=None,
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found",
        )
    return {"id": user.id, "is_active": user.is_active}


@router.post("/{user_id}/force-logout")
async def force_logout(
    user_id: int,
    _admin: User = Depends(require_step_up("users.force_logout")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Revoke every admin session for ``user_id`` and record a
    user-level revoke marker in Redis that auth middleware can
    check on refresh.
    """
    from app.core.redis import get_redis_client

    target = await UserRepository(session).get_by_id(user_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found",
        )

    now = datetime.now(UTC)
    revoked = await AdminSessionRepository(
        session
    ).revoke_all_active_for_user(user_id)

    try:
        redis = get_redis_client()
        await redis.set(
            f"user:force_logout:{user_id}",
            str(int(now.timestamp())),
            ex=60 * 60 * 24 * 30,
        )
    except Exception:
        logger.debug(
            "force_logout_redis_marker_failed",
            user_id=user_id,
        )

    await dispatch_alert(
        event_type="user_force_logout",
        severity="info",
        title="User sessions revoked",
        details=(
            f"target_user_id={user_id}, "
            f"admin_sessions_revoked={revoked}"
        ),
        user_id=_admin.id,
    )
    return {
        "user_id": user_id,
        "admin_sessions_revoked": revoked,
    }


# [REGULATORY-DISABLED v1] admin → user DM отключена вместе с
# чат-стеком (ст. 10.1 149-ФЗ). Восстановить вместе с
# `app/api/v1/chats.py` / `app/api/v1/messages.py`. См.
# `docs/REGULATORY_DISABLED.md`.
# @router.post("/{user_id}/message")
# async def send_admin_message(
#     user_id: int,
#     text: str = Body(..., embed=True, min_length=1, max_length=4000),
#     admin: User = Depends(require_step_up("users.message")),
#     session: AsyncSession = Depends(get_db),
# ) -> dict[str, Any]:
#     ...  # см. git history


@router.post("/{user_id}/grant-admin")
async def grant_admin(
    user_id: int,
    _admin: User = Depends(require_step_up("users.grant_admin")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    service = AdminService(session)
    user = await service.update_user(
        user_id,
        display_name=None,
        is_active=None,
        is_admin=True,
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found",
        )
    await dispatch_alert(
        event_type="admin_role_granted",
        severity="warning",
        title="Admin role granted",
        details=(f"target_user_id={user_id}, " f"granted_by={_admin.id}"),
        user_id=_admin.id,
    )
    return {"id": user.id, "is_admin": user.is_admin}


@router.post("/{user_id}/revoke-admin")
async def revoke_admin(
    user_id: int,
    _admin: User = Depends(require_step_up("users.revoke_admin")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    service = AdminService(session)
    user = await service.update_user(
        user_id,
        display_name=None,
        is_active=None,
        is_admin=False,
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found",
        )
    await dispatch_alert(
        event_type="admin_role_revoked",
        severity="warning",
        title="Admin role revoked",
        details=(f"target_user_id={user_id}, " f"revoked_by={_admin.id}"),
        user_id=_admin.id,
    )
    return {"id": user.id, "is_admin": user.is_admin}


@router.post("/{user_id}/grant-capability")
async def grant_capability(
    user_id: int,
    capability: str = Body(..., embed=True, min_length=2, max_length=64),
    admin: User = Depends(require_step_up("users.grant_capability")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if capability not in KNOWN_CAPABILITIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="unknown capability",
        )
    target = await UserRepository(session).get_by_id(user_id)
    if not target or not target.is_admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user is not admin",
        )
    cap_repo = AdminCapabilityRepository(session)
    if await cap_repo.find_grant(user_id, capability) is not None:
        return {
            "user_id": user_id,
            "capability": capability,
            "granted": False,
        }
    await cap_repo.grant(
        user_id=user_id,
        capability=capability,
        granted_by=admin.id,
    )
    await dispatch_alert(
        event_type="admin_capability_granted",
        severity="info",
        title="Admin capability granted",
        details=(f"target_user_id={user_id}, " f"capability={capability}"),
        user_id=admin.id,
    )
    return {
        "user_id": user_id,
        "capability": capability,
        "granted": True,
    }


@router.post("/{user_id}/revoke-capability")
async def revoke_capability(
    user_id: int,
    capability: str = Body(..., embed=True, min_length=2, max_length=64),
    admin: User = Depends(require_step_up("users.revoke_capability")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    cap_repo = AdminCapabilityRepository(session)
    row = await cap_repo.find_grant(user_id, capability)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="capability row not found",
        )
    await cap_repo.revoke(row)
    return {
        "user_id": user_id,
        "capability": capability,
        "revoked": True,
    }


@router.get("/{user_id}/capabilities")
async def list_capabilities(
    user_id: int,
    _admin: User = Depends(require_admin_session),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows = await AdminCapabilityRepository(session).list_grants_for_user(
        user_id
    )
    return {
        "items": [
            {
                "capability": row.capability,
                "granted_by": row.granted_by,
                "granted_at": row.granted_at,
            }
            for row in rows
        ]
    }
