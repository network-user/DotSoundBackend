# Чат B-pre — PrivateCore: feature_provider stub

## Корень workspace

`C:\Users\User\PycharmProjects\DotSoundPrivateCore`

Не открывать в этом чате: `DotSoundBackend`, `DotSoundComputeWorker`, `DotSoundBot`.

## Цель

Публичный **opaque** слой вычисления «внутренних» признаков и сходства для будущего compute pipeline: детерминистские stub-реализации (`feature_version="metadata-v1"`), без имён сторонних ML-библиотек и моделей в коде, комментариях, тестах и сообщениях коммитов.

## Содержимое (ориентир)

- Новый модуль `dotsound_private_core/services/feature_provider.py`:
  - `compute_track_audio_features(audio_path, *, metadata=None)` — при отсутствии файла может опираться на metadata для stub.
  - `compute_artist_features(artist_id, tracks)`
  - `build_artist_similarity(seed, candidates, top_k)`
  - `build_track_similarity(seed, candidates, top_k)`
- При необходимости публичные **dataclass** результаты (в `recommendation_engine.py` или рядом) — имена нейтральные, например результат трека с полями вектор, highlight_start_sec, mood_tags, tempo_bpm, energy, feature_version.
- `dotsound_private_core/services/__init__.py` — re-export публичного API.
- Тесты: `tests/services/test_feature_provider_stub.py` или зеркало `tests/dotsound_private_core/services/...` по конвенции репо.

## Коммит (одна строка)

```
feat(recsys): add opaque feature_provider stubs
```

## Pytest (из корня PrivateCore)

```
pytest -q tests/services/test_feature_provider_stub.py
```

(Путь к тесту поправь под фактическую структуру `tests/` в PrivateCore.)

## Промпт для вставки в новый чат

```
Открой: C:\Users\User\PycharmProjects\DotSoundBackend\docs\recsys-parallel\02-track-b-pre-privatecore.md
Workspace только DotSoundPrivateCore. Реализуй stub feature_provider и тесты по файлу. CLAUDE black-box: без раскрытия внутренних стадий и провайдеров. Один коммит с сообщением из файла.
```

## Конфликты

Можно выполнять **параллельно с чатом A** (другой репозиторий). Перед merge убедись, что Backend Phase 5 (чат B1) ожидает те же импорты/сигнатуры — при расхождении поправь либо B-pre, либо B1 в ревью.

---

## После успеха всего recsys-спринта

Удаление handoff-файлов делается в **DotSoundBackend** (там лежит `docs/recsys-parallel/`): см. [README.md](README.md) → «Уборка».