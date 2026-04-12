from __future__ import annotations

import asyncio
import io
import json
import struct
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


async def process_voice(
    data: bytes,
) -> tuple[bytes, int, list[float]]:
    with tempfile.TemporaryDirectory() as tmp:
        in_path = Path(tmp) / "input"
        out_path = Path(tmp) / "output.ogg"
        in_path.write_bytes(data)

        proc = await asyncio.create_subprocess_exec(
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
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            logger.error(
                "ffmpeg_voice_failed",
                returncode=proc.returncode,
                stderr=stderr.decode(errors="replace")[
                    :500
                ],
            )
            raise RuntimeError("Voice encoding failed")

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
    proc = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    info = json.loads(stdout)
    return int(
        float(info["format"].get("duration", 0))
    )


async def _get_waveform(
    path: str,
    bars: int = 100,
) -> list[float]:
    proc = await asyncio.create_subprocess_exec(
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
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()

    if not stdout:
        return [0.0] * bars

    samples = struct.unpack(
        f"<{len(stdout) // 2}h", stdout
    )
    chunk = max(1, len(samples) // bars)
    result: list[float] = []
    for i in range(bars):
        start = i * chunk
        end = min(start + chunk, len(samples))
        if start >= len(samples):
            result.append(0.0)
            continue
        peak = max(abs(s) for s in samples[start:end])
        result.append(round(peak / 32768.0, 3))

    max_val = max(result) if result else 1.0
    if max_val > 0:
        result = [
            round(v / max_val, 3) for v in result
        ]
    return result
