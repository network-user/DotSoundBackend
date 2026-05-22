from unittest.mock import MagicMock

from app.config import AppSettings
from app.services.public_web_urls import (
    build_artist_profile_web_url,
    build_user_profile_web_url,
    resolve_mini_app_web_base,
)


def _settings(**kwargs: str) -> AppSettings:
    base = {
        "database_url": "postgresql+asyncpg://u:p@localhost/db",
        "redis_url": "redis://localhost",
        "minio_endpoint": "localhost:9000",
        "minio_access_key": "k",
        "minio_secret_key": "s",
        "minio_bucket": "b",
        "jwt_secret": "test-secret",
    }
    base.update(kwargs)
    return AppSettings(**base)


def test_resolve_mini_app_web_base_from_request() -> None:
    settings = _settings(mini_app_url="")
    request = MagicMock()
    request.base_url = "https://dotsound.example/"
    assert (
        resolve_mini_app_web_base(settings, request)
        == "https://dotsound.example/mini_app"
    )


def test_build_user_profile_web_url_appends_mini_app_root() -> None:
    settings = _settings(mini_app_url="https://dotsound.example")
    assert (
        build_user_profile_web_url(settings, 42)
        == "https://dotsound.example/mini_app/profile/42"
    )


def test_build_user_profile_web_url_keeps_configured_root() -> None:
    settings = _settings(
        mini_app_url="https://dotsound.example/mini_app",
    )
    assert (
        build_user_profile_web_url(settings, 7)
        == "https://dotsound.example/mini_app/profile/7"
    )


def test_build_artist_profile_web_url() -> None:
    settings = _settings(
        mini_app_url="https://dotsound.example/mini_app/",
    )
    assert (
        build_artist_profile_web_url(settings, 3)
        == "https://dotsound.example/mini_app/artist/3"
    )
