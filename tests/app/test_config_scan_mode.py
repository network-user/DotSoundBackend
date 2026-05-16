import pytest
from pydantic import ValidationError

from app.config import AppSettings


_MINIMAL_BASE = dict(
    _env_file=None,
    database_url="sqlite://",
    redis_url="redis://localhost",
    minio_endpoint="localhost:9000",
    minio_access_key="key",
    minio_secret_key="secret",
    minio_bucket="bucket",
    internal_api_allowed_cidrs="10.0.0.0/8",
    jwt_secret="unit-test-jwt-secret-not-for-prod",
    debug=True,
)


def test_scan_mode_accepts_none() -> None:
    s = AppSettings(
        **_MINIMAL_BASE,
        upload_malware_scan_mode="none",
    )
    assert s.upload_malware_scan_mode == "none"


def test_scan_mode_accepts_lightweight() -> None:
    s = AppSettings(
        **_MINIMAL_BASE,
        upload_malware_scan_mode="lightweight",
    )
    assert s.upload_malware_scan_mode == "lightweight"


def test_scan_mode_accepts_clamav() -> None:
    s = AppSettings(
        **_MINIMAL_BASE,
        upload_malware_scan_mode="clamav",
    )
    assert s.upload_malware_scan_mode == "clamav"


def test_scan_mode_rejects_invalid() -> None:
    with pytest.raises(ValidationError):
        AppSettings(
            **_MINIMAL_BASE,
            upload_malware_scan_mode="invalid",
        )
