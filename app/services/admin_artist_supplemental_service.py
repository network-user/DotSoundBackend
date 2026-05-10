"""Admin service for artist supplemental prompt/import workflow."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artist import Artist
from app.repositories.artist_supplemental_info import (
    ArtistSupplementalInfoRepository,
)

_CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")

_BIO_SNIPPET_LEN = 300

_BATCH_PROMPT_HEADER = """\
Ты — музыкальный редактор платформы DotSound (российская музыкальная платформа).
Для каждого артиста из списка напиши краткую справку для карточки артиста.

Правила:
— 3–5 предложений на артиста
— Язык текста: если у артиста метка [RU] — пиши на русском; если [EN] — пиши на русском, \
но адаптируй контекст для русскоязычной аудитории
— Используй country и bio_hint как источник фактов; не придумывай даты и факты если их нет
— Нейтральный информационный стиль, без превосходных степеней и рекламных оборотов
— Текст должен быть полезен пользователю карточки артиста на платформе DotSound

Верни ответ СТРОГО в формате JSON (без пояснений, только JSON):
{{
  "artists": [
    {{"id": 123, "content": "Описание..."}},
    {{"id": 456, "content": "Описание..."}}
  ]
}}

Список артистов:
{artist_list}\
"""


class AdminArtistSupplementalService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ArtistSupplementalInfoRepository(session)

    async def batch_prompt(self, artist_ids: list[int]) -> tuple[str, int]:
        artists = await self._load_artists(artist_ids)
        lines = [_format_artist_line(a) for a in artists]
        prompt = _BATCH_PROMPT_HEADER.format(
            artist_list="\n".join(lines) if lines else "(нет артистов)",
        )
        return prompt, len(artists)

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
                artist_id = int(raw_id)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                errors.append(f"Skipped malformed entry: {entry!r}")
                continue
            if not isinstance(content, str) or not content.strip():
                errors.append(
                    f"artist_id={artist_id}: empty or missing content"
                )
                continue
            await self._repo.upsert(
                artist_id,
                status="done",
                content=content.strip(),
                fetched_at=datetime.now(UTC),
            )
            imported += 1
        return imported, errors

    async def _load_artists(self, artist_ids: list[int]) -> list[Artist]:
        result = await self._session.execute(
            select(Artist).where(Artist.id.in_(artist_ids))
        )
        by_id = {a.id: a for a in result.scalars().all()}
        return [by_id[i] for i in artist_ids if i in by_id]


def _detect_language(name: str | None) -> str:
    return "ru" if _CYRILLIC_RE.search(name or "") else "en"


def _format_artist_line(artist: Artist) -> str:
    lang = _detect_language(artist.name)
    lang_label = "[RU]" if lang == "ru" else "[EN]"
    country = artist.country or "—"
    bio_hint = "—"
    if artist.bio and artist.bio.strip():
        snippet = artist.bio.strip()
        if len(snippet) > _BIO_SNIPPET_LEN:
            snippet = snippet[:_BIO_SNIPPET_LEN] + "…"
        bio_hint = snippet
    return (
        f"— ID: {artist.id} {lang_label} | "
        f"Имя: {artist.name} | "
        f"country: {country} | "
        f"bio_hint: {bio_hint}"
    )


def _parse_ai_response(
    raw: str,
) -> tuple[list[dict[str, Any]], str | None]:
    text = raw.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict) and isinstance(
            data.get("artists"), list
        ):
            return data["artists"], None
        return [], "Parsed JSON but no 'artists' array found"
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            if isinstance(data, dict) and isinstance(
                data.get("artists"), list
            ):
                return data["artists"], None
        except json.JSONDecodeError:
            pass

    return [], "Could not parse JSON from the provided response"
