from __future__ import annotations

from starlette.requests import Request

from app.config import AppSettings

_MINI_APP_ROOT = "/mini_app"


def resolve_mini_app_web_base(
    settings: AppSettings,
    request: Request | None = None,
) -> str:
    configured = (settings.mini_app_url or "").rstrip("/")
    if configured:
        return configured
    if request is None:
        return _MINI_APP_ROOT
    origin = str(request.base_url).rstrip("/")
    return f"{origin}{_MINI_APP_ROOT}"


def _with_mini_app_root(base: str) -> str:
    root = base.rstrip("/")
    if root.endswith(_MINI_APP_ROOT):
        return root
    return f"{root}{_MINI_APP_ROOT}"


def build_user_profile_web_url(
    settings: AppSettings,
    user_id: int,
    *,
    request: Request | None = None,
) -> str:
    base = _with_mini_app_root(
        resolve_mini_app_web_base(settings, request),
    )
    return f"{base}/profile/{user_id}"


def build_artist_profile_web_url(
    settings: AppSettings,
    artist_id: int,
    *,
    request: Request | None = None,
) -> str:
    base = _with_mini_app_root(
        resolve_mini_app_web_base(settings, request),
    )
    return f"{base}/artist/{artist_id}"
