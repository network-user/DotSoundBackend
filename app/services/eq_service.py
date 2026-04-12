import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.eq_settings import (
    EqSettingsRepository,
)
from app.schemas.eq import (
    EqSettingsResponse,
)

logger: structlog.stdlib.BoundLogger = (
    structlog.get_logger(__name__)
)

_EQ_DEFAULT = [0, 0, 0, 0, 0, 0, 0, 0]


class EqService:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._repo = EqSettingsRepository(session)

    async def get_settings(
        self,
        user_id: int,
    ) -> EqSettingsResponse:
        eq = await self._repo.get_by_user_id(user_id)
        if not eq:
            return EqSettingsResponse(
                preset="Flat",
                bands=_EQ_DEFAULT,
            )
        return EqSettingsResponse(
            preset=eq.preset or "Flat",
            bands=[float(v) for v in eq.bands],
        )

    async def save_settings(
        self,
        user_id: int,
        preset: str | None,
        bands: list[float],
    ) -> EqSettingsResponse:
        eq = await self._repo.get_by_user_id(user_id)
        if eq:
            eq.preset = preset
            eq.bands = bands
            await self._repo._session.flush()
        else:
            await self._repo.create(
                user_id=user_id,
                preset=preset,
                bands=bands,
            )

        logger.info(
            "eq_settings_saved",
            user_id=user_id,
            preset=preset,
        )
        return EqSettingsResponse(
            preset=preset or "Flat",
            bands=bands,
        )
