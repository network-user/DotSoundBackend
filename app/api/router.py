from fastapi import APIRouter

from app.api.v1 import (
    account,
    admin,
    albums,
    artists,
    auth,
    auth_email,
    bandcamp,
    blocks,
    complaints,
    dislikes,
    follows,
    health,
    imports,
    likes,
    linked_accounts,
    lyrics,
    metadata,
    notifications,
    onboarding,
    playlists,
    recommendations,
    search,
    signals,
    soundcloud,
    track_preview,
    tracks,
    users,
    ws,
    youtube,
)

# [REGULATORY-DISABLED v1] peer-to-peer обмен сообщениями отключён
# во избежание попадания под ст. 10.1 149-ФЗ (ОРИ). См.
# `docs/REGULATORY_DISABLED.md`. Восстановить после оформления
# юрлица и регистрации в реестре ОРИ Роскомнадзора.
# from app.api.v1 import chats, colisten, comments, messages
from app.api.v1 import (
    prefetch as prefetch_router,
)
from app.api.v1.internal import audio_compute, compute_jobs

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(auth_email.router)
api_router.include_router(auth_email.router_2fa)
api_router.include_router(account.router)
api_router.include_router(users.router)
api_router.include_router(tracks.router)
api_router.include_router(likes.router)
api_router.include_router(dislikes.router)
api_router.include_router(playlists.router)
api_router.include_router(soundcloud.router)
api_router.include_router(track_preview.router)
api_router.include_router(youtube.router)
api_router.include_router(bandcamp.router)
api_router.include_router(complaints.router, tags=["complaints"])
api_router.include_router(metadata.router)
api_router.include_router(admin.router)
api_router.include_router(lyrics.router)
api_router.include_router(follows.router)
api_router.include_router(albums.router)
api_router.include_router(imports.router)
api_router.include_router(linked_accounts.router)
# [REGULATORY-DISABLED v1] см. блок импорта выше.
# api_router.include_router(chats.router)
# api_router.include_router(colisten.router)
# api_router.include_router(messages.router)
# api_router.include_router(comments.router)
api_router.include_router(blocks.router)
api_router.include_router(notifications.router)
api_router.include_router(onboarding.router)
api_router.include_router(recommendations.router)
api_router.include_router(search.router)
api_router.include_router(signals.router)
api_router.include_router(artists.router)
api_router.include_router(prefetch_router.router)
api_router.include_router(audio_compute.router)
api_router.include_router(compute_jobs.router)
api_router.include_router(ws.router)
