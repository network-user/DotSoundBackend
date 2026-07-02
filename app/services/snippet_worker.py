from __future__ import annotations

import asyncio
import os
import shutil
import tempfile

import structlog
from dotsound_private_core.services.snippet_policy import (
    allow_snippet_for_catalog,
)

from app import config as _cfg
from app.core import s3
from app.core.db import AsyncSessionLocal
from app.core.tkq import broker
from app.models.track import Track
from app.models.track_snippet import TrackSnippet
from app.services import compute_queue_service as q
from app.services.compute_job_dispatcher import (
    LocalComputeJob,
    dispatch_compute_job,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def transcode_snippet_local(
    job: LocalComputeJob,
) -> dict:
    snippet_id = int(job.target_id or job.payload.get("snippet_id") or 0)
    structlog.contextvars.bind_contextvars(snippet_id=snippet_id)
    ext_ok = _cfg.settings.snippet_external_catalog_allowed
    async with AsyncSessionLocal() as session:
        sn = await session.get(TrackSnippet, snippet_id)
        if not sn:
            return {"status": "not_found"}
        tr = await session.get(Track, sn.track_id)
        if not tr or not tr.file_key:
            sn.status = "failed"
            sn.error_message = "no_ugc_file"
            await session.commit()
            return {"status": "failed", "error": "no_ugc_file"}
        if not allow_snippet_for_catalog(
            tr.catalog_type,
            allow_external=ext_ok,
        ):
            sn.status = "failed"
            sn.error_message = "catalog_gated"
            await session.commit()
            return {"status": "failed", "error": "catalog_gated"}
        file_key = tr.file_key
    tmpd = tempfile.mkdtemp()
    in_path = os.path.join(tmpd, "in")
    out_path = os.path.join(tmpd, "out.mp3")
    try:
        # Исходник — полный трек; стримим на диск вместо полной
        # буферизации в RAM (ffmpeg читает файл).
        await s3.download_object_to_file(file_key, in_path)
        start = float(sn.start_ms) / 1000.0
        dur = (float(sn.end_ms) - float(sn.start_ms)) / 1000.0
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{start:.3f}",
            "-i",
            in_path,
            "-t",
            f"{dur:.3f}",
            "-map",
            "0:a:0",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "128k",
            out_path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, err = await proc.communicate()
        if proc.returncode != 0:
            async with AsyncSessionLocal() as s2:
                s2_sn = await s2.get(TrackSnippet, snippet_id)
            if s2_sn:
                s2_sn.status = "failed"
                s2_sn.error_message = err.decode(errors="replace")[-200:]
                await s2.commit()
            return {"status": "failed", "error": "ffmpeg_failed"}
        with open(out_path, "rb") as f:
            out_b = f.read()
        if not out_b:
            async with AsyncSessionLocal() as s2:
                s2_sn = await s2.get(TrackSnippet, snippet_id)
            if s2_sn:
                s2_sn.status = "failed"
                s2_sn.error_message = "empty"
                await s2.commit()
            return {"status": "failed", "error": "empty"}
        k = await s3.upload_audio(
            out_b,
            "mp3",
            "audio/mpeg",
            int(sn.user_id),
        )
        async with AsyncSessionLocal() as s3_:
            srow = await s3_.get(TrackSnippet, snippet_id)
            if srow:
                srow.file_key = k
                srow.status = "ready"
                await s3_.commit()
        return {"status": "ready", "file_key": k}
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)


@broker.task
async def transcode_snippet_task(
    snippet_id: int,
) -> None:
    async with AsyncSessionLocal() as session:
        await dispatch_compute_job(
            session,
            job_type=q.JOB_TRACK_SNIPPET,
            target_kind=q.TARGET_KIND_SNIPPET,
            target_id=snippet_id,
            payload={"snippet_id": snippet_id},
            local_handler=transcode_snippet_local,
        )
        await session.commit()
