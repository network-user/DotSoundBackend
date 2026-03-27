from fastapi import APIRouter

from app.api.v1 import health, likes, playlists, tracks, users

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(users.router)
api_router.include_router(tracks.router)
api_router.include_router(likes.router)
api_router.include_router(playlists.router)
