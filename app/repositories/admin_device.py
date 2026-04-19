from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_device import AdminDevice


class AdminDeviceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_fingerprint(
        self, user_id: int, fingerprint_hash: str
    ) -> AdminDevice | None:
        result = await self._session.execute(
            select(AdminDevice).where(
                AdminDevice.user_id == user_id,
                AdminDevice.fingerprint_hash == fingerprint_hash,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, device_id: int) -> AdminDevice | None:
        result = await self._session.execute(
            select(AdminDevice).where(AdminDevice.id == device_id)
        )
        return result.scalar_one_or_none()

    async def list_active_for_user(self, user_id: int) -> list[AdminDevice]:
        result = await self._session.execute(
            select(AdminDevice)
            .where(
                AdminDevice.user_id == user_id,
                AdminDevice.revoked_at.is_(None),
            )
            .order_by(AdminDevice.last_seen_at.desc().nulls_last())
        )
        return list(result.scalars().all())

    async def create_pending(
        self,
        *,
        user_id: int,
        fingerprint_hash: str,
        label: str | None,
        ip: str | None,
        ua: str | None,
    ) -> AdminDevice:
        now = datetime.now(UTC)
        device = AdminDevice(
            user_id=user_id,
            fingerprint_hash=fingerprint_hash,
            label=label,
            ip_first=ip,
            ua_first=ua,
            trusted_at=None,
            last_seen_at=None,
            revoked_at=None,
            created_at=now,
        )
        self._session.add(device)
        await self._session.flush()
        return device

    async def trust(self, device: AdminDevice) -> AdminDevice:
        now = datetime.now(UTC)
        device.trusted_at = now
        device.last_seen_at = now
        device.revoked_at = None
        await self._session.flush()
        return device

    async def touch(
        self,
        device: AdminDevice,
        *,
        ip: str | None = None,
    ) -> AdminDevice:
        device.last_seen_at = datetime.now(UTC)
        if ip is not None and not device.ip_first:
            device.ip_first = ip
        await self._session.flush()
        return device

    async def revoke(self, device: AdminDevice) -> AdminDevice:
        device.revoked_at = datetime.now(UTC)
        await self._session.flush()
        return device
