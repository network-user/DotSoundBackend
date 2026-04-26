from __future__ import annotations

import pytest

from app.config import AppSettings

_REQUIRED_ENV = {
    "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
    "REDIS_URL": "redis://localhost:6379/0",
    "MINIO_ENDPOINT": "localhost:9000",
    "MINIO_ACCESS_KEY": "minioadmin",
    "MINIO_SECRET_KEY": "minioadmin",
    "MINIO_BUCKET": "test-bucket",
    "INTERNAL_API_ALLOWED_CIDRS": "10.0.0.0/8",
}


def _make_settings(
    monkeypatch: pytest.MonkeyPatch,
    **overrides: str,
) -> AppSettings:
    for key, val in {
        **_REQUIRED_ENV, **overrides
    }.items():
        monkeypatch.setenv(key, val)
    return AppSettings(
        _env_file=None,  # type: ignore[call-arg]
    )


def test_allowed_origins_list_parses_csv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = _make_settings(
        monkeypatch,
        ALLOWED_ORIGINS="http://a.com,http://b.com,http://c.com",
    )

    assert cfg.allowed_origins_list == [
        "http://a.com",
        "http://b.com",
        "http://c.com",
    ]


def test_allowed_origins_list_single_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = _make_settings(
        monkeypatch,
        ALLOWED_ORIGINS="http://only.one",
    )

    assert cfg.allowed_origins_list == [
        "http://only.one"
    ]


def test_allowed_origins_list_strips_whitespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = _make_settings(
        monkeypatch,
        ALLOWED_ORIGINS=" http://a.com , http://b.com ",
    )

    assert cfg.allowed_origins_list == [
        "http://a.com",
        "http://b.com",
    ]


def test_allowed_origins_list_skips_empty_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = _make_settings(
        monkeypatch,
        ALLOWED_ORIGINS="http://a.com,,  ,http://b.com,",
    )

    assert cfg.allowed_origins_list == [
        "http://a.com",
        "http://b.com",
    ]


def test_default_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = _make_settings(monkeypatch)

    assert cfg.jwt_expire_days == 7
    assert cfg.debug is False
    assert cfg.allowed_origins == "*"
    assert cfg.log_level == "INFO"
    assert cfg.complaint_threshold == 3
    assert cfg.minio_use_ssl is False
    assert cfg.redact_logs is True
    assert cfg.redact_log_identifiers is True
    assert cfg.tor_log_outbound_public_ip is False
    assert cfg.tor_pool_enabled is False
    assert cfg.elasticsearch_url == "http://127.0.0.1:9200"
    assert cfg.elasticsearch_fallback_to_postgres_on_zero is True


def test_elasticsearch_url_empty_in_env_disables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = _make_settings(
        monkeypatch,
        ELASTICSEARCH_URL="",
    )

    assert cfg.elasticsearch_url == ""


def test_elasticsearch_fallback_to_postgres_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = _make_settings(
        monkeypatch,
        ELASTICSEARCH_FALLBACK_TO_POSTGRES_ON_ZERO="false",
    )

    assert cfg.elasticsearch_fallback_to_postgres_on_zero is False


def test_env_overrides_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = _make_settings(
        monkeypatch,
        JWT_EXPIRE_DAYS="30",
        DEBUG="true",
        LOG_LEVEL="DEBUG",
        LOG_THIRD_PARTY_LEVEL="ERROR",
    )

    assert cfg.jwt_expire_days == 30
    assert cfg.debug is True
    assert cfg.log_level == "DEBUG"
    assert cfg.log_third_party_level == "ERROR"


def test_allowed_origins_wildcard_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = _make_settings(monkeypatch)

    assert cfg.allowed_origins_list == ["*"]
