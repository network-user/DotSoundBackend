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
    chats,
    comments,
    complaints,
    dislikes,
    follows,
    health,
    imports,
    likes,
    linked_accounts,
    lyrics,
    messages,
    metadata,
    notifications,
    onboarding,
    playlists,
    recommendations,
    search,
    signals,
    soundcloud,
    tracks,
    users,
    ws,
    youtube,
)
from app.api.v1.internal import audio_compute

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
api_router.include_router(chats.router)
api_router.include_router(messages.router)
api_router.include_router(comments.router)
api_router.include_router(blocks.router)
api_router.include_router(notifications.router)
api_router.include_router(onboarding.router)
api_router.include_router(recommendations.router)
api_router.include_router(search.router)
api_router.include_router(signals.router)
api_router.include_router(artists.router)
api_router.include_router(audio_compute.router)
api_router.include_router(ws.router)
