from fastapi import APIRouter

from app.api.v1 import (
    complaints,
    health,
    likes,
    dislikes,
    playlists,
    tracks,
    users,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(users.router)
api_router.include_router(tracks.router)
api_router.include_router(likes.router)
api_router.include_router(dislikes.router)
api_router.include_router(playlists.router)
api_router.include_router(
    complaints.router, tags=["complaints"]
)
