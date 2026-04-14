from unittest.mock import patch

import pytest

from app.services.scan_service import (
    ScanResult,
    ScanVerdict,
    scan_bytes,
)

pytestmark = pytest.mark.anyio


async def test_scan_mode_none() -> None:
    with patch(
        "app.services.scan_service.settings"
    ) as mock_settings:
        mock_settings.upload_malware_scan_mode = (
            "none"
        )
        result = await scan_bytes(
            b"data", "file.mp3"
        )
    assert result.verdict == ScanVerdict.SKIPPED


async def test_scan_mode_lightweight() -> None:
    with patch(
        "app.services.scan_service.settings"
    ) as mock_settings:
        mock_settings.upload_malware_scan_mode = (
            "lightweight"
        )
        result = await scan_bytes(
            b"data", "file.mp3"
        )
    assert result.verdict == ScanVerdict.CLEAN


async def test_scan_mode_clamav_stub() -> None:
    with patch(
        "app.services.scan_service.settings"
    ) as mock_settings:
        mock_settings.upload_malware_scan_mode = (
            "clamav"
        )
        result = await scan_bytes(
            b"data", "file.mp3"
        )
    assert result.verdict == ScanVerdict.CLEAN


def test_scan_result_frozen() -> None:
    r = ScanResult(verdict=ScanVerdict.CLEAN)
    with pytest.raises(AttributeError):
        r.verdict = ScanVerdict.INFECTED  # type: ignore[misc]
