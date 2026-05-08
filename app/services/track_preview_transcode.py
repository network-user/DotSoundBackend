from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
import tempfile

import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_FFMPEG_TIMEOUT_SEC = 30.0


async def transcode_http_audio_to_fmp4_aac(
    source_url: str, start_sec: float, duration_sec: float
) -> bytes:
    tmpd = tempfile.mkdtemp()
    out_path = os.path.join(tmpd, "out.mp4")
    proc: asyncio.subprocess.Process | None = None
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
        try:
            _out, err = await asyncio.wait_for(
                proc.communicate(),
                timeout=_FFMPEG_TIMEOUT_SEC,
            )
        except TimeoutError as exc:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(proc.wait(), timeout=2.0)
            logger.warning(
                "track_preview_ffmpeg_timeout",
                timeout_sec=_FFMPEG_TIMEOUT_SEC,
            )
            raise RuntimeError("ffmpeg timeout") from exc
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
        if proc is not None and proc.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(proc.wait(), timeout=2.0)
        shutil.rmtree(tmpd, ignore_errors=True)
