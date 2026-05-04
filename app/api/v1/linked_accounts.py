"""OAuth account linking — connect/disconnect Spotify, SoundCloud, VK."""

from __future__ import annotations

import secrets
import urllib.parse
from typing import Any

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.rate_limit import limiter
from app.core.redis import get_redis_client
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.services.linked_account_service import LinkedAccountService

router = APIRouter(prefix="/linked-accounts", tags=["linked-accounts"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_SUPPORTED_PROVIDERS = frozenset({"spotify", "soundcloud"})
_STATE_PREFIX = "oauth_state:"


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class LinkedAccountResponse(BaseModel):
    provider: str
    provider_username: str | None
    provider_user_id: str | None
    connected: bool

    class Config:
        from_attributes = True


class ConnectResponse(BaseModel):
    auth_url: str


class LinkedPlaylistItem(BaseModel):
    id: str
    name: str
    track_count: int | None = None
    description: str | None = None
    cover_url: str | None = None


class LinkedPlaylistsResponse(BaseModel):
    playlists: list[LinkedPlaylistItem]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assert_provider(provider: str) -> None:
    if provider not in _SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider: {provider}. Supported: "
                   f"{', '.join(sorted(_SUPPORTED_PROVIDERS))}",
        )


def _build_auth_url(provider: str, state: str) -> str:
    if provider == "spotify":
        params = urllib.parse.urlencode(
            {
                "client_id": settings.spotify_client_id,
                "response_type": "code",
                "redirect_uri": settings.spotify_redirect_uri,
                "state": state,
                "scope": (
                    "user-library-read user-read-private playlist-read-private"
                ),
            }
        )
        return f"https://accounts.spotify.com/authorize?{params}"

    if provider == "soundcloud":
        params = urllib.parse.urlencode(
            {
                "client_id": settings.soundcloud_oauth_client_id,
                "redirect_uri": settings.soundcloud_oauth_redirect_uri,
                "response_type": "code",
                "state": state,
                "scope": "non-expiring",
            }
        )
        return f"https://soundcloud.com/connect?{params}"

    # vk
    params = urllib.parse.urlencode(
        {
            "client_id": settings.vk_app_id,
            "redirect_uri": settings.vk_redirect_uri,
            "scope": "audio",
            "response_type": "code",
            "state": state,
            "v": "5.131",
        }
    )
    return f"https://oauth.vk.com/authorize?{params}"


async def _exchange_code(
    provider: str, code: str
) -> dict[str, Any]:
    """Exchange an authorization code for tokens. Returns token dict."""
    timeout = 15.0

    if provider == "spotify":
        import base64

        creds = base64.b64encode(
            f"{settings.spotify_client_id}:"
            f"{settings.spotify_client_secret}".encode()
        ).decode()
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(
                "https://accounts.spotify.com/api/token",
                headers={
                    "Authorization": f"Basic {creds}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.spotify_redirect_uri,
                },
            )
            r.raise_for_status()
            return r.json()

    if provider == "soundcloud":
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(
                "https://secure.soundcloud.com/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": settings.soundcloud_oauth_client_id,
                    "client_secret": settings.soundcloud_oauth_client_secret,
                    "redirect_uri": settings.soundcloud_oauth_redirect_uri,
                },
            )
            r.raise_for_status()
            return r.json()

    # vk — token exchange via GET
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(
            "https://oauth.vk.com/access_token",
            params={
                "client_id": settings.vk_app_id,
                "client_secret": settings.vk_app_secret,
                "redirect_uri": settings.vk_redirect_uri,
                "code": code,
            },
        )
        r.raise_for_status()
        return r.json()


async def _fetch_provider_profile(
    provider: str, access_token: str
) -> dict[str, str | None]:
    """Return {provider_user_id, provider_username}."""
    timeout = 10.0
    try:
        if provider == "spotify":
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.get(
                    "https://api.spotify.com/v1/me",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                r.raise_for_status()
                d = r.json()
            return {
                "provider_user_id": d.get("id"),
                "provider_username": d.get("display_name") or d.get("id"),
            }

        if provider == "soundcloud":
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.get(
                    "https://api-v2.soundcloud.com/me",
                    headers={"Authorization": f"OAuth {access_token}"},
                    params={"client_id": settings.soundcloud_oauth_client_id},
                )
                r.raise_for_status()
                d = r.json()
            return {
                "provider_user_id": str(d.get("id", "")),
                "provider_username": d.get("username") or d.get("full_name"),
            }

        # vk — user_id is returned in token response; fetch name separately
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(
                "https://api.vk.com/method/users.get",
                params={
                    "access_token": access_token,
                    "v": "5.131",
                    "fields": "screen_name",
                },
            )
            r.raise_for_status()
            items = (r.json().get("response") or [{}])
            u = items[0] if items else {}
        return {
            "provider_user_id": str(u.get("id", "")),
            "provider_username": (
                u.get("screen_name")
                or f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
                or None
            ),
        }
    except Exception as exc:
        logger.warning(
            "provider_profile_fetch_failed",
            provider=provider,
            error=str(exc),
        )
        return {"provider_user_id": None, "provider_username": None}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=list[LinkedAccountResponse])
@limiter.limit("30/minute")
async def list_linked_accounts(
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[LinkedAccountResponse]:
    svc = LinkedAccountService(session)
    accounts = await svc.list_accounts(current_user.id)
    connected = {a.provider for a in accounts}
    result = [
        LinkedAccountResponse(
            provider=a.provider,
            provider_username=a.provider_username,
            provider_user_id=a.provider_user_id,
            connected=True,
        )
        for a in accounts
    ]
    # Add not-yet-connected providers so the UI knows what's available
    for p in sorted(_SUPPORTED_PROVIDERS - connected):
        result.append(
            LinkedAccountResponse(
                provider=p,
                provider_username=None,
                provider_user_id=None,
                connected=False,
            )
        )
    return result


@router.post(
    "/{provider}/connect",
    response_model=ConnectResponse,
)
@limiter.limit("10/minute")
async def connect_provider(
    request: Request,
    provider: str,
    current_user: User = Depends(get_current_user),
) -> ConnectResponse:
    _assert_provider(provider)

    if provider == "spotify" and not settings.spotify_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Spotify OAuth is not configured",
        )
    if provider == "soundcloud" and not settings.soundcloud_oauth_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SoundCloud OAuth is not configured",
        )
    if provider == "vk" and not settings.vk_app_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VK OAuth is not configured",
        )

    state = secrets.token_urlsafe(32)
    redis = get_redis_client()
    await redis.setex(
        f"{_STATE_PREFIX}{state}",
        settings.oauth_state_ttl_seconds,
        f"{provider}:{current_user.id}",
    )
    auth_url = _build_auth_url(provider, state)
    return ConnectResponse(auth_url=auth_url)


@router.get("/{provider}/callback")
async def oauth_callback(
    request: Request,
    provider: str,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    session: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    frontend_base = settings.mini_app_url or ""
    success_url = f"{frontend_base}/settings/connections?connected={provider}"
    error_url = f"{frontend_base}/settings/connections?error=oauth_failed&provider={provider}"

    _assert_provider(provider)

    if error:
        logger.info("oauth_provider_error", provider=provider, error=error)
        return RedirectResponse(url=error_url)

    if not code or not state:
        return RedirectResponse(url=error_url)

    # Validate state
    redis = get_redis_client()
    state_key = f"{_STATE_PREFIX}{state}"
    stored = await redis.getdel(state_key)
    if not stored:
        logger.warning("oauth_invalid_state", provider=provider)
        return RedirectResponse(url=error_url)

    stored_provider, _, user_id_str = stored.partition(":")
    if stored_provider != provider:
        return RedirectResponse(url=error_url)

    try:
        user_id = int(user_id_str)
    except ValueError:
        return RedirectResponse(url=error_url)

    # Exchange code for tokens
    try:
        token_data = await _exchange_code(provider, code)
    except Exception as exc:
        logger.warning("oauth_code_exchange_failed", provider=provider, error=str(exc))
        return RedirectResponse(url=error_url)

    if "error" in token_data:
        logger.warning("oauth_token_error", provider=provider, data=token_data)
        return RedirectResponse(url=error_url)

    access_token: str = token_data.get("access_token", "")
    refresh_token: str | None = token_data.get("refresh_token")
    expires_in: int | None = token_data.get("expires_in")

    # Fetch provider profile
    profile = await _fetch_provider_profile(provider, access_token)

    # Persist tokens
    svc = LinkedAccountService(session)
    try:
        await svc.upsert_account(
            user_id=user_id,
            provider=provider,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            scopes=token_data.get("scope"),
            provider_user_id=profile["provider_user_id"],
            provider_username=profile["provider_username"],
        )
    except Exception as exc:
        logger.error(
            "oauth_account_save_failed",
            provider=provider,
            error=str(exc),
        )
        return RedirectResponse(url=error_url)

    logger.info(
        "oauth_account_connected",
        user_id=user_id,
        provider=provider,
        username=profile.get("provider_username"),
    )
    return RedirectResponse(url=success_url)


@router.delete("/{provider}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def disconnect_provider(
    request: Request,
    provider: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    _assert_provider(provider)
    svc = LinkedAccountService(session)
    await svc.delete_account(current_user.id, provider)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{provider}/playlists",
    response_model=LinkedPlaylistsResponse,
)
@limiter.limit("10/minute")
async def list_provider_playlists(
    request: Request,
    provider: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LinkedPlaylistsResponse:
    """Return the user's playlists from a connected provider account."""
    _assert_provider(provider)

    svc = LinkedAccountService(session)
    account = await svc.get_account(current_user.id, provider)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{provider.capitalize()} account is not connected. "
                "Connect it first in account settings."
            ),
        )
    account = await svc.refresh_if_expired(account)
    access_token, _ = svc.get_decrypted_tokens(account)

    import asyncio

    from dotsound_private_core.services import fetch_user_playlists

    client_id = (
        settings.soundcloud_oauth_client_id
        if provider == "soundcloud"
        else ""
    )
    raw = await asyncio.to_thread(
        fetch_user_playlists,
        provider,
        access_token,
        client_id=client_id,
    )
    playlists = [
        LinkedPlaylistItem(
            id=p["id"],
            name=p["name"],
            track_count=p.get("track_count"),
            description=p.get("description"),
            cover_url=p.get("cover_url"),
        )
        for p in raw
    ]
    return LinkedPlaylistsResponse(playlists=playlists)
