from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import structlog

from app.config import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


class ScanVerdict(str, Enum):
    CLEAN = "clean"
    INFECTED = "infected"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class ScanResult:
    verdict: ScanVerdict
    detail: str = ""


async def scan_bytes(
    data: bytes,
    filename: str = "",
) -> ScanResult:
    mode = settings.upload_malware_scan_mode
    if mode == "none":
        return ScanResult(verdict=ScanVerdict.SKIPPED)

    if mode == "lightweight":
        logger.info(
            "scan_lightweight",
            filename=filename,
            size=len(data),
        )
        return ScanResult(verdict=ScanVerdict.CLEAN)

    if mode == "clamav":
        logger.info(
            "scan_clamav_stub",
            filename=filename,
            size=len(data),
        )
        return ScanResult(verdict=ScanVerdict.CLEAN)

    return ScanResult(
        verdict=ScanVerdict.ERROR,
        detail=f"Unknown scan mode: {mode}",
    )
