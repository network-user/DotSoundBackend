"""Admin API package — combines tracks, users, and complaints sub-routers."""

from fastapi import APIRouter

from . import complaints, tracks, users

router = APIRouter(prefix="/admin", tags=["admin"])
router.include_router(tracks.router)
router.include_router(users.router)
router.include_router(complaints.router)
