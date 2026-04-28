"""Admin API package — combines all admin sub-routers."""

from fastapi import APIRouter

from . import (
    artist_catalog,
    audio_compute,
    audit,
    auth,
    complaints,
    dashboard,
    genre_samples,
    logs,
    manifest,
    metrics,
    security,
    system,
    tasks,
    tracks,
    users,
    users_extended,
    ws,
)

router = APIRouter(prefix="/admin", tags=["admin"])
router.include_router(artist_catalog.router)
router.include_router(tracks.router)
router.include_router(genre_samples.router)
router.include_router(users.router)
router.include_router(users_extended.router)
router.include_router(complaints.router)
router.include_router(manifest.router)
router.include_router(audio_compute.router)
router.include_router(auth.router)
router.include_router(dashboard.router)
router.include_router(system.router)
router.include_router(logs.router)
router.include_router(metrics.router)
router.include_router(tasks.router)
router.include_router(audit.router)
router.include_router(security.router)
router.include_router(ws.router)
