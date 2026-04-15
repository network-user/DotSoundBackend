from __future__ import annotations

import asyncio
import io
import json
import struct
import subprocess
import tempfile
from pathlib import Path

import structlog
from PIL import Image

from app.config import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(
    __name__
)


def strip_metadata_and_compress(
    data: bytes,
    max_size: int,
    quality: int | None = None,
) -> tuple[bytes, int, int]:
    quality = quality or settings.image_quality
    img = Image.open(io.BytesIO(data))

    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
    else:
        img = img.convert("RGB")

    w, h = img.size
    if max(w, h) > max_size:
        ratio = max_size / max(w, h)
        w = int(w * ratio)
        h = int(h * ratio)
        img = img.resize((w, h), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(
        buf,
        format="WEBP",
        quality=quality,
        method=4,
    )
    logger.debug(
        "image_processed",
        original_bytes=len(data),
        result_bytes=buf.tell(),
        width=w,
        height=h,
    )
    return buf.getvalue(), w, h


def create_thumbnail(
    data: bytes,
    size: int | None = None,
) -> bytes:
    size = size or settings.image_thumbnail_size
    img = Image.open(io.BytesIO(data))
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
    else:
        img = img.convert("RGB")
    img.thumbnail((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=60)
    return buf.getvalue()


def process_image(
    data: bytes,
    max_size: int | None = None,
) -> tuple[bytes, bytes, int, int]:
    ms = max_size or settings.image_chat_max_size
    processed, w, h = strip_metadata_and_compress(
        data, ms
    )
    thumb = create_thumbnail(processed)
    return processed, thumb, w, h


def _ffmpeg_available() -> bool:
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=5,
        )
        return True
    except (FileNotFoundError, OSError):
        return False


_HAS_FFMPEG: bool | None = None


def _check_ffmpeg() -> bool:
    global _HAS_FFMPEG  # noqa: PLW0603
    if _HAS_FFMPEG is None:
        _HAS_FFMPEG = _ffmpeg_available()
        if not _HAS_FFMPEG:
            logger.warning(
                "ffmpeg_not_found",
                hint="voice messages will be "
                "stored without conversion",
            )
    return _HAS_FFMPEG


def _run_ffmpeg(
    *args: str,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        args,
        capture_output=True,
    )


async def process_voice(
    data: bytes,
) -> tuple[bytes, int, list[float]]:
    if not _check_ffmpeg():
        logger.info("voice_passthrough_no_ffmpeg")
        return data, 0, [0.5] * 50

    with tempfile.TemporaryDirectory() as tmp:
        in_path = Path(tmp) / "input"
        out_path = Path(tmp) / "output.ogg"
        in_path.write_bytes(data)

        result = await asyncio.to_thread(
            _run_ffmpeg,
            "ffmpeg",
            "-i",
            str(in_path),
            "-ac",
            "1",
            "-ar",
            "48000",
            "-c:a",
            "libopus",
            "-b:a",
            settings.voice_bitrate,
            "-vn",
            "-t",
            str(settings.voice_max_duration),
            str(out_path),
            "-y",
        )

        if result.returncode != 0:
            logger.error(
                "ffmpeg_voice_failed",
                returncode=result.returncode,
                stderr=result.stderr.decode(
                    errors="replace"
                )[:500],
            )
            return data, 0, [0.5] * 50

        ogg_data = out_path.read_bytes()
        duration = await _get_duration(
            str(out_path)
        )
        waveform = await _get_waveform(
            str(in_path)
        )

    logger.debug(
        "voice_processed",
        original_bytes=len(data),
        result_bytes=len(ogg_data),
        duration=duration,
    )
    return ogg_data, duration, waveform


async def _get_duration(path: str) -> int:
    if not _check_ffmpeg():
        return 0
    try:
        result = await asyncio.to_thread(
            _run_ffmpeg,
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            path,
        )
        info = json.loads(result.stdout)
        return int(
            float(
                info["format"].get("duration", 0)
            )
        )
    except Exception:
        return 0


async def _get_waveform(
    path: str,
    bars: int = 100,
) -> list[float]:
    if not _check_ffmpeg():
        return [0.5] * bars
    try:
        result = await asyncio.to_thread(
            _run_ffmpeg,
            "ffmpeg",
            "-i",
            path,
            "-ac",
            "1",
            "-ar",
            "8000",
            "-f",
            "s16le",
            "-",
        )
        stdout = result.stdout

        if not stdout:
            return [0.0] * bars

        samples = struct.unpack(
            f"<{len(stdout) // 2}h", stdout
        )
        chunk = max(1, len(samples) // bars)
        waveform: list[float] = []
        for i in range(bars):
            start = i * chunk
            end = min(
                start + chunk, len(samples)
            )
            if start >= len(samples):
                waveform.append(0.0)
                continue
            peak = max(
                abs(s)
                for s in samples[start:end]
            )
            waveform.append(
                round(peak / 32768.0, 3)
            )

        max_val = (
            max(waveform) if waveform else 1.0
        )
        if max_val > 0:
            waveform = [
                round(v / max_val, 3)
                for v in waveform
            ]
        return waveform
    except Exception:
        return [0.5] * bars
