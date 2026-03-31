from fastapi import APIRouter

from app.api.v1 import (
    admin,
    auth,
    complaints,
    dislikes,
    health,
    likes,
    metadata,
    playlists,
    soundcloud,
    tracks,
    users,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(tracks.router)
api_router.include_router(likes.router)
api_router.include_router(dislikes.router)
api_router.include_router(playlists.router)
api_router.include_router(soundcloud.router)
api_router.include_router(complaints.router, tags=["complaints"])
api_router.include_router(metadata.router)
api_router.include_router(admin.router)
