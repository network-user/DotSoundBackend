"""Tracks API package — discovery, user uploads, and playback sub-routers.

Route registration order matters: /my and /upload must be included before
/{track_id} to prevent the wildcard from swallowing fixed-path routes.
"""

from fastapi import APIRouter

from . import discovery as discovery
from . import edit_context as edit_context
from . import hls as hls
from . import info as info
from . import playback as playback
from . import prefetch as prefetch
from . import processing as processing
from . import upload_chunked as upload_chunked
from . import user as user

router = APIRouter(prefix="/tracks", tags=["tracks"])
router.include_router(discovery.router)
router.include_router(upload_chunked.router)  # /upload/* + /check-duplicate
router.include_router(user.router)
router.include_router(prefetch.router)  # before wildcard /{track_id} routes
router.include_router(hls.router)
router.include_router(playback.router)
router.include_router(info.router)
router.include_router(edit_context.router)
