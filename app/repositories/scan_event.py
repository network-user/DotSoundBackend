from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scan_event import ScanEvent


class ScanEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def log(
        self,
        *,
        filename: str,
        file_size: int | None,
        verdict: str,
        threat_name: str | None,
        scan_mode: str,
    ) -> ScanEvent:
        event = ScanEvent(
            filename=filename,
            file_size=file_size,
            verdict=verdict,
            threat_name=threat_name,
            scan_mode=scan_mode,
            scanned_at=datetime.now(UTC),
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def stats(self) -> dict[str, int]:
        rows = await self._session.execute(
            select(ScanEvent.verdict, func.count().label("n")).group_by(
                ScanEvent.verdict
            )
        )
        counts: dict[str, int] = {}
        for verdict, n in rows:
            counts[verdict] = n
        return counts

    async def list_events(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        verdict: str | None = None,
    ) -> list[ScanEvent]:
        q = select(ScanEvent).order_by(ScanEvent.scanned_at.desc())
        if verdict:
            q = q.where(ScanEvent.verdict == verdict)
        q = q.limit(limit).offset(offset)
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def count_events(
        self,
        *,
        verdict: str | None = None,
    ) -> int:
        q = select(func.count()).select_from(ScanEvent)
        if verdict:
            q = q.where(ScanEvent.verdict == verdict)
        result = await self._session.execute(q)
        return result.scalar_one()
