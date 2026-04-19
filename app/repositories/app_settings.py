from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_setting import AppSetting

FEATURE_FLAG_PREFIX = "feature."


class AppSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, key: str) -> AppSetting | None:
        result = await self._session.execute(
            select(AppSetting).where(AppSetting.key == key)
        )
        return result.scalar_one_or_none()

    async def get_value(
        self,
        key: str,
        default: Any = None,  # noqa: ANN401
    ) -> Any:  # noqa: ANN401
        row = await self.get(key)
        if row is None:
            return default
        return row.value

    async def upsert(
        self,
        *,
        key: str,
        value: dict[str, Any],
        updated_by: int | None,
    ) -> AppSetting:
        row = await self.get(key)
        now = datetime.now(UTC)
        if row is None:
            row = AppSetting(
                key=key,
                value=value,
                updated_by=updated_by,
                updated_at=now,
            )
            self._session.add(row)
        else:
            row.value = value
            row.updated_by = updated_by
            row.updated_at = now
        await self._session.flush()
        return row

    async def list_by_prefix(self, prefix: str) -> list[AppSetting]:
        result = await self._session.execute(
            select(AppSetting)
            .where(AppSetting.key.like(f"{prefix}%"))
            .order_by(AppSetting.key)
        )
        return list(result.scalars().all())

    async def get_feature_flag(self, name: str, default: bool = False) -> bool:
        value = await self.get_value(
            f"{FEATURE_FLAG_PREFIX}{name}",
            default={"enabled": default},
        )
        if isinstance(value, dict):
            raw = value.get("enabled", default)
            return bool(raw)
        return bool(value)

    async def set_feature_flag(
        self,
        name: str,
        enabled: bool,
        updated_by: int | None,
    ) -> AppSetting:
        return await self.upsert(
            key=f"{FEATURE_FLAG_PREFIX}{name}",
            value={"enabled": bool(enabled)},
            updated_by=updated_by,
        )

    async def list_feature_flags(
        self,
    ) -> list[AppSetting]:
        return await self.list_by_prefix(FEATURE_FLAG_PREFIX)
