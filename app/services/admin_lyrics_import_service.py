"""Admin service for batch lyrics prompt/import workflows."""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lyrics import TrackLyrics
from app.models.track import Track
from app.repositories.lyrics import LyricsRepository

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)

_BATCH_PROMPT_TEMPLATE = """\
Ты — музыкальный редактор DotSound.
Для каждого трека ниже найди и верни оригинальный текст песни.

Правила:
— Верни только текст песни (без комментариев, анализа и markdown)
— Сохраняй переносы строк между строчками/куплетами
— Не добавляй таймкоды, метки [Verse], [Chorus] и т.п.
— Если текста нет, верни пустую строку

Ответ строго JSON:
{{
  "tracks": [
    {{"id": 123, "lyrics": "line 1\\nline 2\\n..."}},
    {{"id": 456, "lyrics": ""}}
  ]
}}

Список треков:
{track_list}\
"""


class AdminLyricsImportService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = LyricsRepository(session)

    async def build_prompt_for_tracks(
        self, track_ids: list[int]
    ) -> tuple[str, int]:
        tracks = await self._load_tracks_by_ids(track_ids)
        prompt = _BATCH_PROMPT_TEMPLATE.format(
            track_list=_render_track_lines(tracks),
        )
        return prompt, len(tracks)

    async def build_prompt_for_filtered_tracks(
        self,
        *,
        search: str | None,
        only_without_lyrics: bool,
        limit: int,
    ) -> tuple[str, int]:
        tracks = await self._load_filtered_tracks(
            search=search,
            only_without_lyrics=only_without_lyrics,
            limit=limit,
        )
        prompt = _BATCH_PROMPT_TEMPLATE.format(
            track_list=_render_track_lines(tracks),
        )
        return prompt, len(tracks)

    async def import_ai_response(
        self,
        *,
        raw_response: str,
        skip_existing: bool,
    ) -> tuple[int, list[str]]:
        entries, parse_error = _parse_ai_response(raw_response)
        if parse_error:
            return 0, [parse_error]

        imported = 0
        errors: list[str] = []
        for entry in entries:
            track_id_raw = entry.get("id")
            try:
                track_id = int(track_id_raw)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                errors.append(f"Skipped malformed entry: {entry!r}")
                continue

            lyrics_text_raw = (
                entry.get("lyrics")
                if "lyrics" in entry
                else entry.get("plain_text", entry.get("content"))
            )
            if not isinstance(lyrics_text_raw, str):
                errors.append(f"track_id={track_id}: missing lyrics text")
                continue

            normalized_text = _normalize_lyrics_text(lyrics_text_raw)
            if not normalized_text:
                errors.append(f"track_id={track_id}: empty lyrics text")
                continue

            track = await self._session.get(Track, track_id)
            if track is None:
                errors.append(f"track_id={track_id}: track not found")
                continue
            if not track.is_active:
                errors.append(f"track_id={track_id}: track inactive")
                continue

            existing = await self._repo.get_by_track_id(track_id)
            if skip_existing and existing is not None:
                errors.append(
                    f"track_id={track_id}: skipped (lyrics already exist)"
                )
                continue

            await self._repo.create_or_update(
                track_id=track_id,
                plain_text=normalized_text,
                source="manual",
                synced_lines=None,
            )
            imported += 1

        if imported > 0:
            await self._session.commit()
        return imported, errors

    async def _load_tracks_by_ids(self, track_ids: list[int]) -> list[Track]:
        if not track_ids:
            return []
        stmt = select(Track).where(Track.id.in_(track_ids))
        result = await self._session.execute(stmt)
        by_id = {track.id: track for track in result.scalars().all()}
        return [by_id[track_id] for track_id in track_ids if track_id in by_id]

    async def _load_filtered_tracks(
        self,
        *,
        search: str | None,
        only_without_lyrics: bool,
        limit: int,
    ) -> list[Track]:
        stmt: Select[tuple[Track]] = (
            select(Track)
            .order_by(Track.created_at.desc())
            .limit(limit)
        )
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                Track.title.ilike(pattern) | Track.artist.ilike(pattern)
            )
        if only_without_lyrics:
            stmt = (
                stmt.outerjoin(
                    TrackLyrics,
                    TrackLyrics.track_id == Track.id,
                )
                .where(TrackLyrics.id.is_(None))
            )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


def _render_track_lines(tracks: list[Track]) -> str:
    if not tracks:
        return "(нет треков)"
    lines = []
    for track in tracks:
        artist = track.artist or "Unknown"
        lines.append(
            f"— ID: {track.id} | Artist: {artist} | Title: {track.title}"
        )
    return "\n".join(lines)


def _normalize_lyrics_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    lines = [line.rstrip() for line in normalized.split("\n")]
    return "\n".join(lines).strip()


def _parse_ai_response(raw: str) -> tuple[list[dict[str, Any]], str | None]:
    text = raw.strip()

    try:
        data = json.loads(text)
        if isinstance(data, dict) and isinstance(data.get("tracks"), list):
            return data["tracks"], None
        return [], "Parsed JSON but no 'tracks' array found"
    except json.JSONDecodeError:
        pass

    match = _JSON_BLOCK_RE.search(text)
    if match:
        try:
            data = json.loads(match.group())
            if isinstance(data, dict) and isinstance(data.get("tracks"), list):
                return data["tracks"], None
        except json.JSONDecodeError:
            pass

    return [], "Could not parse JSON from the provided response"
