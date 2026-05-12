"""Admin API package — combines all admin sub-routers."""

from fastapi import APIRouter

from app.config import settings

from . import (
    albums as admin_albums,
)
from . import (
    antivirus,
    artist_catalog,
    artist_discography,
    audio_compute,
    audit,
    auth,
    complaints,
    dashboard,
    experiments,
    recsys,
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
from . import (
    playlists as admin_playlists,
)

router = APIRouter(
    prefix=settings.admin_panel_route_prefix,
    tags=["admin"],
)
router.include_router(artist_catalog.router)
router.include_router(artist_discography.router)
router.include_router(admin_albums.router)
router.include_router(admin_playlists.router)
router.include_router(tracks.router)
router.include_router(genre_samples.router)
router.include_router(users.router)
router.include_router(users_extended.router)
router.include_router(complaints.router)
router.include_router(manifest.router)
router.include_router(audio_compute.router)
router.include_router(auth.router)
router.include_router(dashboard.router)
router.include_router(experiments.router)
router.include_router(recsys.router)
router.include_router(system.router)
router.include_router(logs.router)
router.include_router(metrics.router)
router.include_router(tasks.router)
router.include_router(audit.router)
router.include_router(security.router)
router.include_router(antivirus.router)
router.include_router(ws.router)
