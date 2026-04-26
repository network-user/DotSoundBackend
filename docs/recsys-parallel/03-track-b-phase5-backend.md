# Чат B1 — Phase 5.1–5.5: только DotSoundBackend

## Предусловия

1. В **основной ветке** (или целевой для интеграции) уже **смержен чат A** (Phase 1): head Alembic ≥ `0059`, в коде есть модели/сервисы превью (не обязательно для логики compute, но миграция 0060 должна иметь `down_revision = "0059"`).
2. Желательно смержен **чат B-pre** (PrivateCore), если Backend будет импортировать новые символы из PrivateCore в этом PR; иначе временно не импортировать новое из PC в этом коммите (только таблицы и очередь).

## Корень workspace

`C:\Users\User\PycharmProjects\DotSoundBackend`

Не трогать: `DotSoundBot`. Worker — в отдельном чате [04-track-b-phase5-worker.md](04-track-b-phase5-worker.md).

## Цель

Generic **compute_jobs** (таблица из 0057): типы задач для аудио-признаков, артиста, similarity, catalog normalize; internal HTTP **рядом** с ASR, но отдельным роутером `app/api/v1/internal/compute_jobs.py` (префикс вида `/internal/compute/...` под `/api/v1`); HMAC как в `app/services/compute_worker_service.py` + паттерн `audio_compute.py`; запись результатов через `compute_results_router.py`; post-upload enqueue в `upload_service.py`; CLI `python -m app.cli.compute_backfill`; интеграция `track_features_builder.py` с таблицей `track_audio_features`.

## Декомпозиция

1. **Миграция** `alembic/versions/0060_recsys_compute_outputs.py` (`down_revision = "0059"`):
  `track_audio_features`, `artist_features`, `artist_similarity`, `track_similarity` (поля по спецификации в `.cursor/rules/context_delete.txt`, блок COMMIT 2).
2. **ORM** для новых таблиц в `app/models/`.
3. `**compute_queue_service.py`:** константы job types, `KNOWN_JOB_TYPES`, `enqueue_`*, `queue_health_snapshot`.
4. `**app/api/v1/internal/compute_jobs.py`:** heartbeat, claim (body job_types), progress, result, fail, GET status; верификация через общий слой с `audio_compute` (вынести `_verify` при DRY).
5. `**app/services/compute_results_router.py`:** `persist_result(session, job, result)` по `job_type`.
6. `**upload_service.py`:** после создания трека — enqueue (идемпотентно) как минимум track audio features + catalog normalize (приоритеты по плану в context_delete).
7. `**app/cli/compute_backfill.py`** + `app/cli/__init__.py`.
8. **Роутер** + проверка allowlist (префикс `/api/v1/internal/` уже покрыт middleware).
9. **Тесты** (имена из context_delete):
  `test_compute_queue_helpers.py`, `test_compute_results_router.py`,  
   `test_compute_jobs.py`, `test_compute_status.py`,  
   `test_upload_post_hook.py`, `test_compute_backfill.py`,  
   `test_recsys_audio_features_integration.py`

## Контракт для чата B2 (Worker)

Зафиксируй в PR описании (или в конце этого файла после реализации) точные пути:

- Base: `/api/v1/internal/compute/...` (уточни фактический `prefix` в роутере).
- Claim request/response JSON поля: `job_id`, `job_type`, `target_kind`, `target_id`, `payload`, `feature_version`, `claim_deadline_at`.
- Заголовки подписи: как у `audio-compute` (`X-Worker-Id`, `X-Timestamp`, `X-Nonce`, `X-Worker-Signature`, …).

Чат B2 не стартует интеграционные тесты против живого API до merge этого PR.

## Коммит (одна строка)

```
feat(compute): add audio/artist/track features + similarity jobs
```

## Pytest (Backend, одна строка)

```
pytest -q tests/app/services/test_compute_queue_helpers.py tests/app/services/test_compute_results_router.py tests/app/api/v1/internal/test_compute_jobs.py tests/app/api/v1/internal/test_compute_status.py tests/app/services/test_upload_post_hook.py tests/app/cli/test_compute_backfill.py tests/app/services/test_recsys_audio_features_integration.py
```

## Промпт для вставки в новый чат

```
Открой: C:\Users\User\PycharmProjects\DotSoundBackend\docs\recsys-parallel\03-track-b-phase5-backend.md
Workspace DotSoundBackend. Предусловия из файла обязательны. Реализуй только Backend-часть Phase 5; Worker не трогать. CLAUDE.md, AGENTS.md; .env не читать. Коммит и pytest — как в файле. В конце допиши в этот же md-файл секцию «Зафиксированный контракт API» с реальными путями и примерами JSON для чата B2.
```

## Конфликты

Не параллелить с **чатом A** на одной ветке. С **чатом B2** на одном репо не конфликтует (разные репо); на одной ветке Backend — только один активный PR B1.

## Зафиксированный контракт API (B2, после B1)

База URL (относительно origin API): `https://<host>`.

Префикс роутера: **`/internal/compute`**. С учётом глобального `api_router` full path:
**`/api/v1/internal/compute/...`**.

### Эндпойнты (все, кроме `GET` audio, с телом, подписанные HMAC)

| Метод | Path |
|-------|------|
| POST | `/api/v1/internal/compute/workers/heartbeat` |
| POST | `/api/v1/internal/compute/jobs/claim` |
| POST | `/api/v1/internal/compute/jobs/{job_id}/progress` |
| POST | `/api/v1/internal/compute/jobs/{job_id}/result` |
| POST | `/api/v1/internal/compute/jobs/{job_id}/fail` |
| GET | `/api/v1/internal/compute/status` |

`GET` без тела, подпись считается по **пустому** body.

### OTT-загрузка MP3 (как ASR, без HMAC в теле)

| Метод | Path |
|-------|------|
| GET | `/api/v1/internal/compute/jobs/{job_id}/audio?ott=...` |

Только для `job_type=track_audio_features` в ответе `claim` в поле `audio_url` (относительный path + `?ott=`).

### Заголовки подписи (как `audio-compute`)

- `X-Worker-Id` — id воркера из `compute_workers`
- `X-Timestamp` — unix seconds (строка)
- `X-Nonce` — уникальная одноразовая строка
- `X-Worker-Signature` — HMAC-SHA256 hex: те же поля, что `compute_worker_service` (path = `request.url.path`, body = raw bytes)
- опционально: `X-Worker-Signature-Version` = `1`

`GET` audio: те же `X-Worker-Id` + `ott` query, без HMAC-POST.

### `POST /jobs/claim`

**Request JSON:**

```json
{
  "job_types": [
    "track_audio_features",
    "artist_features_update",
    "artist_similarity_index",
    "track_similarity_index",
    "catalog_ingest_normalize"
  ]
}
```

`job_types` — непустой список строк. Неизвестные типы игнорируются при `claim_next` (очередь по пересечению).

**200** — взяли job:

```json
{
  "job_id": "cj_...",
  "job_type": "track_audio_features",
  "target_kind": "track",
  "target_id": "42",
  "payload": null,
  "feature_version": "v1",
  "claim_deadline_at": "2026-01-01T12:00:00+00:00",
  "audio_url": "/api/v1/internal/compute/jobs/cj_.../audio?ott=..."
}
```

`audio_url` только при `track_audio_features`.

**204** — очередь пуста по данным `job_types`.

### `GET /status`

**200** — агрегат очереди:

```json
{
  "by_type": {
    "track_audio_features": { "pending": 2, "claimed": 0 }
  },
  "oldest_pending_sec": { "track_audio_features": 120.0 }
}
```

(Ключи статусов: `pending`, `claimed`, `succeeded`, `failed` — фактическое множество зависит от данных.)

### `POST /jobs/{job_id}/result` — тела по `job_type` (сводка)

Все варианты: один JSON-объект, совместимый с `persist_result`.

**`track_audio_features`**

```json
{
  "feature_vector": [0.1, 0.2],
  "mood_tags": ["a", "b"],
  "tempo_bpm": 120.0,
  "energy": 0.5,
  "highlight_start_sec": 3.0,
  "feature_version": "v1"
}
```

**`artist_features_update`**

```json
{
  "centroid_vector": [1, 0, 0],
  "dominant_moods": ["calm"],
  "style_tags": ["indie"],
  "feature_version": "v1"
}
```

**`artist_similarity_index` / `track_similarity_index`**

```json
{
  "neighbors": [
    {
      "similar_artist_id": 2,
      "score": 0.85,
      "reason_tags": ["shared_genre"]
    }
  ],
  "feature_version": "v1"
}
```

(Для `track_similarity_index` вместо `similar_artist_id` — `similar_track_id` / `track_id`.)

**`catalog_ingest_normalize`**

```json
{
  "title": "Norm title",
  "artist": "Norm artist",
  "genre": "rock"
}
```

### `POST /jobs/{job_id}/fail`

```json
{ "reason": "io_error" }
```

---

## После успеха всего recsys-спринта

Удали `docs/recsys-parallel/` и секцию в `docs/project_context.md` — [README.md](README.md) → «Уборка».