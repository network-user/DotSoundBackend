from __future__ import annotations

import asyncio
import os
import shutil
import tempfile

import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_FFMPEG_TIMEOUT_SEC = 90.0


async def transcode_http_audio_to_fmp4_aac(
    source_url: str, start_sec: float, duration_sec: float
) -> bytes:
    tmpd = tempfile.mkdtemp()
    out_path = os.path.join(tmpd, "out.mp4")
    try:
        cmd: list[str] = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{float(start_sec):.3f}",
            "-i",
            source_url,
            "-t",
            f"{float(duration_sec):.3f}",
            "-vn",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-f",
            "mp4",
            "-movflags",
            "frag_keyframe+empty_moov",
            out_path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _out, err = await asyncio.wait_for(
            proc.communicate(),
            timeout=_FFMPEG_TIMEOUT_SEC,
        )
        if proc.returncode != 0:
            logger.warning(
                "track_preview_ffmpeg_failed",
                code=proc.returncode,
                stderr=err[:500].decode(
                    errors="replace",
                ),
            )
            raise RuntimeError("ffmpeg failed")
        with open(out_path, "rb") as f:
            data = f.read()
        if not data:
            raise RuntimeError("empty preview output")
        return data
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)
