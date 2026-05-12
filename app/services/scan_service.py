from __future__ import annotations

import asyncio
import io
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
