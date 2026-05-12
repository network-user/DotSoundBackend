from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.scan_service import (
    ScanResult,
    ScanVerdict,
    _clamav_scan_sync,
    scan_bytes,
    scan_s3_key,
)

pytestmark = pytest.mark.anyio

_MOD = "app.services.scan_service"


async def test_scan_mode_none() -> None:
    with patch(f"{_MOD}.settings") as mock_settings:
        mock_settings.upload_malware_scan_mode = "none"
        result = await scan_bytes(b"data", "file.mp3")
    assert result.verdict == ScanVerdict.SKIPPED


async def test_scan_mode_lightweight() -> None:
    with patch(f"{_MOD}.settings") as mock_settings:
        mock_settings.upload_malware_scan_mode = "lightweight"
        result = await scan_bytes(b"data", "file.mp3")
    assert result.verdict == ScanVerdict.CLEAN


async def test_scan_clamav_clean() -> None:
    clean = ScanResult(verdict=ScanVerdict.CLEAN)
    with (
        patch(f"{_MOD}.settings") as mock_settings,
        patch(f"{_MOD}._clamav_scan_sync", return_value=clean),
    ):
        mock_settings.upload_malware_scan_mode = "clamav"
        mock_settings.clamav_host = "localhost"
        mock_settings.clamav_port = 3310
        result = await scan_bytes(b"safe data", "track.mp3")
    assert result.verdict == ScanVerdict.CLEAN


async def test_scan_clamav_infected() -> None:
    infected = ScanResult(
        verdict=ScanVerdict.INFECTED, detail="Eicar-Test-Signature"
    )
    with (
        patch(f"{_MOD}.settings") as mock_settings,
        patch(f"{_MOD}._clamav_scan_sync", return_value=infected),
    ):
        mock_settings.upload_malware_scan_mode = "clamav"
        mock_settings.clamav_host = "localhost"
        mock_settings.clamav_port = 3310
        result = await scan_bytes(b"X5O!P%@AP[4", "eicar.mp3")
    assert result.verdict == ScanVerdict.INFECTED
    assert "Eicar" in result.detail


async def test_scan_clamav_connection_error_fail_closed() -> None:
    with (
        patch(f"{_MOD}.settings") as mock_settings,
        patch(
            f"{_MOD}._clamav_scan_sync",
            side_effect=ConnectionRefusedError("clamd down"),
        ),
        patch(
            "dotsound_private_core.services.upload_policy"
            ".should_reject_on_av_error",
            return_value=True,
        ),
    ):
        mock_settings.upload_malware_scan_mode = "clamav"
        mock_settings.clamav_host = "localhost"
        mock_settings.clamav_port = 3310
        result = await scan_bytes(b"data", "track.mp3")
    assert result.verdict == ScanVerdict.ERROR


async def test_scan_clamav_connection_error_fail_open() -> None:
    with (
        patch(f"{_MOD}.settings") as mock_settings,
        patch(
            f"{_MOD}._clamav_scan_sync",
            side_effect=ConnectionRefusedError("clamd down"),
        ),
        patch(
            "dotsound_private_core.services.upload_policy"
            ".should_reject_on_av_error",
            return_value=False,
        ),
    ):
        mock_settings.upload_malware_scan_mode = "clamav"
        mock_settings.clamav_host = "localhost"
        mock_settings.clamav_port = 3310
        result = await scan_bytes(b"data", "track.mp3")
    assert result.verdict == ScanVerdict.CLEAN


async def test_scan_s3_key_skips_when_mode_none() -> None:
    with patch(f"{_MOD}.settings") as mock_settings:
        mock_settings.upload_malware_scan_mode = "none"
        result = await scan_s3_key("temp/uploads/x/file.mp3")
    assert result.verdict == ScanVerdict.SKIPPED


async def test_scan_s3_key_downloads_and_scans() -> None:
    clean = ScanResult(verdict=ScanVerdict.CLEAN)
    with (
        patch(f"{_MOD}.settings") as mock_settings,
        patch(f"{_MOD}.scan_bytes", new_callable=AsyncMock) as mock_scan,
        patch(
            "app.core.s3.download_object",
            new_callable=AsyncMock,
            return_value=b"audio data",
        ),
    ):
        mock_settings.upload_malware_scan_mode = "clamav"
        mock_scan.return_value = clean
        result = await scan_s3_key(
            "temp/uploads/u1/session/track.mp3", "track.mp3"
        )
    mock_scan.assert_awaited_once_with(b"audio data", "track.mp3")
    assert result.verdict == ScanVerdict.CLEAN


def test_scan_result_frozen() -> None:
    r = ScanResult(verdict=ScanVerdict.CLEAN)
    with pytest.raises(AttributeError):
        r.verdict = ScanVerdict.INFECTED  # type: ignore[misc]


class TestClamavScanSync:
    def _make_cd(self, stream_result: tuple) -> MagicMock:
        cd = MagicMock()
        cd.instream.return_value = {"stream": stream_result}
        return cd

    def test_ok_returns_clean(self) -> None:
        with patch("clamd.ClamdNetworkSocket") as mock_clamd:
            mock_clamd.return_value = self._make_cd(("OK", ""))
            result = _clamav_scan_sync(b"data", "localhost", 3310, 30)
        assert result.verdict == ScanVerdict.CLEAN

    def test_found_returns_infected(self) -> None:
        with patch("clamd.ClamdNetworkSocket") as mock_clamd:
            mock_clamd.return_value = self._make_cd(
                ("FOUND", "Eicar-Test-Signature")
            )
            result = _clamav_scan_sync(b"data", "localhost", 3310, 30)
        assert result.verdict == ScanVerdict.INFECTED
        assert "Eicar" in result.detail

    def test_unknown_verdict_returns_error(self) -> None:
        with patch("clamd.ClamdNetworkSocket") as mock_clamd:
            mock_clamd.return_value = self._make_cd(("ERROR", "oops"))
            result = _clamav_scan_sync(b"data", "localhost", 3310, 30)
        assert result.verdict == ScanVerdict.ERROR
