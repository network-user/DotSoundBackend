"""Admin antivirus endpoints — ClamAV status and scan event history."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, require_capability
from app.models.user import User
from app.repositories.scan_event import ScanEventRepository
from app.services.scan_service import get_clamav_status

router = APIRouter(prefix="/antivirus", tags=["admin-antivirus"])


class ScanEventOut(BaseModel):
    id: int
    filename: str
    file_size: int | None
    verdict: str
    threat_name: str | None
    scan_mode: str
    scanned_at: str

    @classmethod
    def from_orm(cls, obj: Any) -> "ScanEventOut":
        return cls(
            id=obj.id,
            filename=obj.filename,
            file_size=obj.file_size,
            verdict=obj.verdict,
            threat_name=obj.threat_name,
            scan_mode=obj.scan_mode,
            scanned_at=obj.scanned_at.isoformat(),
        )


@router.get("/status")
async def antivirus_status(
    _admin: User = Depends(require_capability("antivirus.view")),
) -> dict[str, Any]:
    return await get_clamav_status()


@router.get("/stats")
async def antivirus_stats(
    _admin: User = Depends(require_capability("antivirus.view")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    repo = ScanEventRepository(session)
    counts = await repo.stats()
    total = sum(counts.values())
    return {
        "total": total,
        "clean": counts.get("clean", 0),
        "infected": counts.get("infected", 0),
        "error": counts.get("error", 0),
        "skipped": counts.get("skipped", 0),
    }


@router.get("/events")
async def antivirus_events(
    _admin: User = Depends(require_capability("antivirus.view")),
    session: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    verdict: str | None = Query(None),
) -> dict[str, Any]:
    repo = ScanEventRepository(session)
    events = await repo.list_events(
        limit=limit, offset=offset, verdict=verdict
    )
    total = await repo.count_events(verdict=verdict)
    return {
        "total": total,
        "items": [ScanEventOut.from_orm(e) for e in events],
    }
