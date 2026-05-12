from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

import structlog

from app.config import settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

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


def _clamav_scan_sync(
    data: bytes,
    host: str,
    port: int,
    timeout: int,
) -> ScanResult:
    import clamd

    cd = clamd.ClamdNetworkSocket(
        host=host, port=port, timeout=timeout
    )
    result = cd.instream(io.BytesIO(data))
    stream_result = result.get("stream", ("ERROR", ""))
    verdict_str = (
        stream_result[0] if stream_result else "ERROR"
    )
    detail = (
        stream_result[1]
        if len(stream_result) > 1
        else ""
    )
    if verdict_str == "OK":
        return ScanResult(verdict=ScanVerdict.CLEAN)
    if verdict_str == "FOUND":
        return ScanResult(
            verdict=ScanVerdict.INFECTED, detail=detail
        )
    return ScanResult(
        verdict=ScanVerdict.ERROR,
        detail=f"Unexpected ClamAV verdict: {verdict_str}",
    )


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
        from dotsound_private_core.services.upload_policy import (
            CLAMAV_SCAN_TIMEOUT_SECONDS,
            should_reject_on_av_error,
        )

        try:
            result = await asyncio.to_thread(
                _clamav_scan_sync,
                data,
                settings.clamav_host,
                settings.clamav_port,
                CLAMAV_SCAN_TIMEOUT_SECONDS,
            )
            logger.info(
                "scan_clamav_complete",
                filename=filename,
                size=len(data),
                verdict=result.verdict,
            )
            return result
        except Exception as exc:
            logger.warning(
                "scan_clamav_error",
                filename=filename,
                error=str(exc),
            )
            if should_reject_on_av_error():
                return ScanResult(
                    verdict=ScanVerdict.ERROR,
                    detail=str(exc),
                )
            return ScanResult(verdict=ScanVerdict.CLEAN)

    return ScanResult(
        verdict=ScanVerdict.ERROR,
        detail=f"Unknown scan mode: {mode}",
    )


async def scan_s3_key(
    s3_key: str,
    filename: str = "",
) -> ScanResult:
    mode = settings.upload_malware_scan_mode
    if mode == "none":
        return ScanResult(verdict=ScanVerdict.SKIPPED)
    from app.core import s3

    data = await s3.download_object(s3_key)
    return await scan_bytes(data, filename)


def _clamav_version_sync(host: str, port: int, timeout: int) -> str:
    import clamd

    cd = clamd.ClamdNetworkSocket(
        host=host, port=port, timeout=timeout
    )
    return cd.version()


async def get_clamav_status() -> dict[str, object]:
    mode = settings.upload_malware_scan_mode
    if mode != "clamav":
        return {
            "reachable": False,
            "mode": mode,
            "version": None,
            "note": "ClamAV mode not active",
        }
    try:
        from dotsound_private_core.services.upload_policy import (
            CLAMAV_SCAN_TIMEOUT_SECONDS,
        )

        version = await asyncio.to_thread(
            _clamav_version_sync,
            settings.clamav_host,
            settings.clamav_port,
            CLAMAV_SCAN_TIMEOUT_SECONDS,
        )
        return {
            "reachable": True,
            "mode": mode,
            "version": version,
            "host": settings.clamav_host,
            "port": settings.clamav_port,
        }
    except Exception as exc:
        return {
            "reachable": False,
            "mode": mode,
            "version": None,
            "host": settings.clamav_host,
            "port": settings.clamav_port,
            "error": str(exc),
        }


async def log_scan_result(
    session: "AsyncSession",
    *,
    filename: str,
    file_size: int | None,
    result: ScanResult,
) -> None:
    from app.repositories.scan_event import ScanEventRepository

    repo = ScanEventRepository(session)
    threat = result.detail if result.verdict == ScanVerdict.INFECTED else None
    await repo.log(
        filename=filename,
        file_size=file_size,
        verdict=result.verdict.value,
        threat_name=threat,
        scan_mode=settings.upload_malware_scan_mode,
    )
