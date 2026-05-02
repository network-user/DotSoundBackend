"""Admin service for track context — prompt generation and batch import."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.models.track_info import TrackInfo
from app.repositories.track_info import TrackInfoRepository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")

_SINGLE_PROMPT_RU = """\
Ты — музыкальный редактор российской музыкальной платформы DotSound.
Напиши краткую информацию о треке для карточки песни.

Трек: «{title}» — {artist}

Требования:
— 3–5 предложений
— История создания или контекст выпуска
— Российский музыкальный и культурный контекст
— Интересный факт или значение для слушателей
— Нейтральный информационный стиль, без превосходных степеней

Ответь только текстом описания, без заголовков.\
"""

_SINGLE_PROMPT_EN = """\
You are a music editor for the DotSound Russian music platform.
Write a brief description for the track card.

Track: "{title}" — {artist}

Requirements:
— 3–5 sentences
— Creation history or release context
— Genre and cultural context, adapted for Russian-speaking audience
— An interesting fact or the song's significance
— Neutral informational style

Reply with only the description text, no headings.\
"""

_BATCH_PROMPT_HEADER = """\
Ты — музыкальный редактор российской музыкальной платформы DotSound.
Для каждого трека из списка напиши краткое описание для карточки песни.

Требования к каждому описанию (3–5 предложений):
— История создания или контекст выпуска (если известно)
— Для российских исполнителей: российский культурный контекст
— Для зарубежных исполнителей: адаптация для русскоязычной аудитории
— Интересный факт или значение песни
— Нейтральный информационный стиль, без превосходных степеней

Верни ответ СТРОГО в формате JSON (без пояснений, только JSON):
{{
  "tracks": [
    {{"id": 123, "content": "Описание..."}},
    {{"id": 456, "content": "Описание..."}}
  ]
}}

Список треков:
{track_list}\
"""


class TrackNotFoundError(Exception):
    def __init__(self, track_id: int) -> None:
        super().__init__(f"Track {track_id} not found")
        self.track_id = track_id


class AdminTrackContextService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = TrackInfoRepository(session)

    async def get_context(self, track_id: int) -> TrackInfo | None:
        return await self._repo.get_by_track_id(track_id)

    async def set_context(self, track_id: int, content: str) -> TrackInfo:
        if await self._load_track(track_id) is None:
            raise TrackNotFoundError(track_id)
        return await self._repo.upsert(
            track_id,
            status="done",
            content=content,
            fetched_at=datetime.now(UTC),
        )

    async def clear_context(self, track_id: int) -> TrackInfo:
        if await self._load_track(track_id) is None:
            raise TrackNotFoundError(track_id)
        return await self._repo.upsert(
            track_id,
            status="not_found",
            content=None,
            fetched_at=datetime.now(UTC),
        )

    async def single_prompt(self, track_id: int) -> tuple[str, str]:
        track = await self._load_track(track_id)
        if track is None:
            raise TrackNotFoundError(track_id)
        lang = _detect_language(track.artist, track.title)
        template = _SINGLE_PROMPT_RU if lang == "ru" else _SINGLE_PROMPT_EN
        prompt = template.format(
            title=track.title,
            artist=track.artist or "Unknown",
        )
        return prompt, lang

    async def batch_prompt(
        self, track_ids: list[int]
    ) -> tuple[str, int]:
        tracks = await self._load_tracks(track_ids)
        lines = [_format_track_line(t) for t in tracks]
        prompt = _BATCH_PROMPT_HEADER.format(
            track_list="\n".join(lines) if lines else "(нет треков)",
        )
        return prompt, len(tracks)

    async def batch_import(
        self, raw_response: str
    ) -> tuple[int, list[str]]:
        entries, parse_error = _parse_ai_response(raw_response)
        if parse_error:
            return 0, [parse_error]

        imported = 0
        errors: list[str] = []
        for entry in entries:
            raw_id = entry.get("id")
            content = entry.get("content")
            try:
                track_id = int(raw_id)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                errors.append(f"Skipped malformed entry: {entry!r}")
                continue
            if not isinstance(content, str) or not content.strip():
                errors.append(
                    f"track_id={track_id}: empty or missing content"
                )
                continue
            try:
                await self._repo.upsert(
                    track_id,
                    status="done",
                    content=content.strip(),
                    fetched_at=datetime.now(UTC),
                )
                imported += 1
            except Exception as exc:
                logger.warning(
                    "batch_import_upsert_failed",
                    track_id=track_id,
                    error=str(exc),
                )
                errors.append(f"track_id={track_id}: {exc}")
        return imported, errors

    async def _load_track(self, track_id: int) -> Track | None:
        result = await self._session.execute(
            select(Track).where(Track.id == track_id)
        )
        return result.scalar_one_or_none()

    async def _load_tracks(self, track_ids: list[int]) -> list[Track]:
        result = await self._session.execute(
            select(Track).where(Track.id.in_(track_ids))
        )
        by_id = {t.id: t for t in result.scalars().all()}
        return [by_id[i] for i in track_ids if i in by_id]


def _detect_language(
    artist: str | None, title: str | None
) -> str:
    combined = f"{artist or ''} {title or ''}"
    return "ru" if _CYRILLIC_RE.search(combined) else "en"


def _format_track_line(track: Track) -> str:
    lang = _detect_language(track.artist, track.title)
    context_label = "RU" if lang == "ru" else "EN"
    artist = track.artist or "Unknown"
    return (
        f"— ID: {track.id} | Исполнитель: {artist} "
        f"| Название: {track.title} | Контекст: {context_label}"
    )


def _parse_ai_response(
    raw: str,
) -> tuple[list[dict[str, Any]], str | None]:
    text = raw.strip()

    try:
        data = json.loads(text)
        if isinstance(data, dict) and isinstance(
            data.get("tracks"), list
        ):
            return data["tracks"], None
        return [], "Parsed JSON but no 'tracks' array found"
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            if isinstance(data, dict) and isinstance(
                data.get("tracks"), list
            ):
                return data["tracks"], None
        except json.JSONDecodeError:
            pass

    return [], "Could not parse JSON from the provided response"
