"""Admin API package — combines tracks, users, and complaints sub-routers."""

from fastapi import APIRouter

from . import audio_compute, complaints, manifest, tracks, users

router = APIRouter(prefix="/admin", tags=["admin"])
router.include_router(tracks.router)
router.include_router(users.router)
router.include_router(complaints.router)
router.include_router(manifest.router)
router.include_router(audio_compute.router)
