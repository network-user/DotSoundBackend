from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_session import AdminSession


class AdminSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: int,
        device_id: int,
        jti: str,
        refresh_jti: str | None,
        ip: str | None,
        ua: str | None,
        ttl_seconds: int,
    ) -> AdminSession:
        now = datetime.now(UTC)
        row = AdminSession(
            user_id=user_id,
            device_id=device_id,
            jti=jti,
            refresh_jti=refresh_jti,
            ip=ip,
            ua=ua,
            created_at=now,
            last_seen_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
            revoked_at=None,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_by_jti(self, jti: str) -> AdminSession | None:
        result = await self._session.execute(
            select(AdminSession).where(AdminSession.jti == jti)
        )
        return result.scalar_one_or_none()

    async def get_by_refresh_jti(
        self, refresh_jti: str
    ) -> AdminSession | None:
        result = await self._session.execute(
            select(AdminSession).where(AdminSession.refresh_jti == refresh_jti)
        )
        return result.scalar_one_or_none()

    async def list_active_for_user(self, user_id: int) -> list[AdminSession]:
        result = await self._session.execute(
            select(AdminSession)
            .where(
                AdminSession.user_id == user_id,
                AdminSession.revoked_at.is_(None),
            )
            .order_by(desc(AdminSession.created_at))
        )
        return list(result.scalars().all())

    async def touch(
        self,
        row: AdminSession,
        *,
        ip: str | None = None,
        ua: str | None = None,
    ) -> AdminSession:
        row.last_seen_at = datetime.now(UTC)
        if ip is not None:
            row.ip = ip
        if ua is not None:
            row.ua = ua
        await self._session.flush()
        return row

    async def rotate_refresh(
        self,
        row: AdminSession,
        *,
        new_refresh_jti: str,
    ) -> AdminSession:
        row.refresh_jti = new_refresh_jti
        await self._session.flush()
        return row

    async def revoke(self, row: AdminSession) -> AdminSession:
        row.revoked_at = datetime.now(UTC)
        await self._session.flush()
        return row

    async def revoke_all_for_device(self, device_id: int) -> int:
        result = await self._session.execute(
            select(AdminSession).where(
                AdminSession.device_id == device_id,
                AdminSession.revoked_at.is_(None),
            )
        )
        rows = list(result.scalars().all())
        now = datetime.now(UTC)
        for row in rows:
            row.revoked_at = now
        await self._session.flush()
        return len(rows)
