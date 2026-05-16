# Handoff: оптимизация очереди задач + офлоад на DotSoundComputeWorker

**Дата:** 2026-05-16  
**Статус:** Phase 1 завершена, Phase 2 (полный офлоад) **не начата**  
**Хаб-репозиторий:** `DotSoundBackend`  
**Связанные репо:** `DotSoundPrivateCore`, `DotSoundComputeWorker`  
**Транскрипт сессии (полный контекст диалога):**  
`C:\Users\User\.cursor\projects\c-Users-User-PycharmProjects-DotSoundBackend\agent-transcripts\f7b5fc48-bdf0-4c4e-8693-1a733dce92eb\f7b5fc48-bdf0-4c4e-8693-1a733dce92eb.jsonl`

---

## 1. Исходная проблема

- В Taskiq-очереди **>21 000** задач (`sync_artist_catalog_task` и др.), backlog растёт.
- В логах массово:
  - `403 Forbidden` на `api-v2.soundcloud.com` (tracks, resolve)
  - `sc_semaphore_timeout` при `soundcloud_global_concurrency=4`
  - `background_job.failed_terminal` на catalog sync
- Пользователь хочет **ускорить обработку** и **разгрузить основной сервер**, передавая часть работы на **DotSoundComputeWorker** (отдельная мощная машина, свой egress IP, опционально proxy per job type).

---

## 2. Решение пользователя (архитектура офлоада)

| Параметр | Выбор |
|----------|--------|
| Где воркер | Отдельная машина у пользователя |
| Scope | **Всё HTTP-bound + CPU-bound** (не только lyrics/ASR) |
| DB у воркера | **Нет** — pull HMAC API Backend → result POST (best practice) |
| SC egress | Чистый IP воркера + proxy по типу задачи (`WORKER_PROXY_BY_TYPE_JSON`) |
| Поведение при сбое | Задача возвращается в общий пул → Backend выполняет **local fallback**; ретраи, reaper для expired lease |
| Порядок | «Оба сразу», но агент сознательно сделал **инкремент**: сначала anti-block + RPC-каркас |

### Целевая модель (ещё не полностью реализована)

```
Taskiq task → compute_job_dispatcher
                 ├─ offloadable → ComputeJob (queued) → Worker claim → handler → result API
                 │                                      └─ fail/timeout → reaper → local fallback
                 └─ local_only  → выполнить на Backend сразу
```

**Универсальный SC RPC** (уже есть каркас): Backend не дублирует каждый SC endpoint — шлёт `method + args`, воркер выполняет HTTP через `OutboundClient`.

---

## 3. Что СДЕЛАНО (Phase 1 + фундамент)

### 3.1 DotSoundPrivateCore

| Файл | Назначение |
|------|------------|
| `services/sc_anti_block_policy.py` | Классификация SC HTTP → action (dead_track, rotate, refresh client_id, rate_limit, transient); TTL, backpressure threshold |
| `services/compute_job_policy.py` | Enum job types, `RoutingMode`, lease/attempts/priority, backoff, `should_fallback_to_local` |
| `contracts/sc_rpc_protocol.py` | `SoundCloudRpcRequest` / `SoundCloudRpcResultEnvelope`, whitelist methods |
| `services/outbound/profiles.py` | Расширены browser profiles (Chrome/Safari variants) |
| `services/playback_streaming_policy.py` | **Untracked** — добавлены алиасы `HLS_MIGRATE_*` для совместимости с Backend (см. §6) |
| `tests/.../test_sc_anti_block_policy.py` | ✅ |
| `tests/.../test_compute_job_policy.py` | ✅ |
| `tests/.../test_sc_rpc_protocol.py` | ✅ |

**Тесты:** `67 passed` (policy + rpc protocol).

### 3.2 DotSoundBackend

| Файл | Назначение |
|------|------------|
| `app/services/sc_dead_track_cache.py` | Redis TTL-кэш «мёртвых» SC треков (404/410) |
| `app/services/sc_browser_session.py` | Адаптер `OutboundClient` + anti-block для **локального** пути |
| `app/services/sc_rpc_client.py` | Enqueue `soundcloud_rpc` + wait Redis envelope + fallback exceptions |
| `app/services/soundcloud_service.py` | `_anti_block_get()`, `SoundCloudTrackUnavailable`, optional offload в `fetch_track_by_ref` |
| `app/services/artist_catalog_sync_worker.py` | Idempotency Redis locks, backpressure, graceful dead tracks |
| `app/services/compute_queue_service.py` | `JOB_SOUNDCLOUD_RPC`, `enqueue_soundcloud_rpc()` |
| `app/services/compute_results_router.py` | `_persist_soundcloud_rpc()` → Redis `sc_rpc_result:{id}` |
| `app/config.py` | `soundcloud_global_concurrency=10`, `sc_offload_enabled=False`, `sc_offload_wait_seconds=30` |
| `docker-compose.yml` | `--max-async-tasks` → `${TASKIQ_MAX_ASYNC_TASKS:-50}` |
| `.env.example` | Документация новых переменных |
| `tests/.../test_sc_dead_track_cache.py` | ✅ 7 tests |
| `tests/.../test_sc_rpc_client.py` | ✅ 6 tests |
| `tests/.../test_compute_results_router.py` | +2 теста для SC RPC persist |

**НЕ созданы:** `compute_job_dispatcher.py`, `compute_job_reaper.py`.

**Alembic для ComputeJob:** не нужна — поля уже достаточны.

### 3.3 DotSoundComputeWorker

| Файл | Назначение |
|------|------------|
| `worker/handlers/soundcloud.py` | `handle_soundcloud_rpc` — OutboundClient + proxy per job type |
| `worker/handlers/__init__.py` | Регистрация `soundcloud_rpc` |
| `worker/config.py` | `default_proxy`, `proxy_by_type_json` |
| `.env.example` | Proxy / concurrency by type |
| `tests/handlers/test_soundcloud_rpc.py` | ✅ 6 tests |

**НЕ созданы:** handlers enrichment, ffmpeg, image; расширения `backend_client.py`.

### 3.4 Как включить SC offload (после деплоя воркера)

1. На ComputeWorker: `WORKER_HANDLES_COMPUTE=true`, зарегистрирован worker, доступен claim API.
2. На Backend: `SC_OFFLOAD_ENABLED=true` в `.env` (пользователь сам — агент **не читает** `.env`).
3. Smoke: один `fetch_track_by_ref` / catalog sync под нагрузкой, смотреть `sc_rpc_offload_*` в логах.

Пока `SC_OFFLOAD_ENABLED=false` (default) — весь SC идёт через **улучшенный локальный** `sc_browser_session` (уже должно снизить 403 vs старый httpx).

---

## 4. Что НЕ СДЕЛАНО (Phase 2 — основная работа)

Выполнять **в порядке зависимостей**:

### Backend

- [ ] **`app/services/compute_job_dispatcher.py`**
  - `create_compute_job(job_type, payload, routing_mode)` по `compute_job_policy`
  - offloadable → insert `ComputeJob`; `LOCAL_ONLY` → вызвать local handler сразу
- [ ] **`app/services/compute_job_reaper.py`**
  - Каждые ~60s: `claimed_until < now` → `queued`, `attempt_count++`
  - Если `attempt_count >= fallback_after` → **local handler** на Backend
  - Подключить в startup worker (docker-compose / lifespan) — **ещё не в compose**
- [ ] **`compute_results_router.py`** — persist handlers для:
  - `sc_artist_catalog_sync`, `sc_artist_similar_station_sync`, `artist_enrichment`,
  - `track_info_fetch`, `external_import_scan`, `track_transcoding`, `track_waveform`,
  - `track_snippet`, `track_cover_processing`
- [ ] **Local fallback handlers** (один модуль или пакет) — вызывают существующую логику + `sc_browser_session`
- [ ] **Taskiq workers → dispatcher mode:**
  - `artist_catalog_sync_worker`, `artist_enrichment_worker`, `track_info_worker`,
  - `external_import_worker`, `cover_worker`, `transcoding`, `waveform_worker`, `snippet_worker`
- [ ] **`app/api/v1/internal/compute_jobs.py`**
  - Claim filter: worker берёт только offloadable types
  - Result endpoint: `error_kind`; `dead_track` → no retry
- [ ] **Тесты:** dispatcher, reaper, dispatcher-mode workers
- [ ] **`lint_all`:** ruff/black/mypy по изменённым файлам во всех 3 репо
- [ ] **Обновить `TODO.md`** во всех репо после завершения

### ComputeWorker

- [ ] `worker/handlers/enrichment.py` — artist_enrichment, track_info_fetch, external_import_scan
- [ ] `worker/handlers/ffmpeg_jobs.py` — transcoding, waveform, snippet
- [ ] `worker/handlers/image_jobs.py` — track_cover_processing (Pillow)
- [ ] `worker/backend_client.py` — `upload_artwork()`, `upload_audio_variant()`
- [ ] `pyproject.toml` — Pillow, python-magic в extra `http`
- [ ] Тесты stubs для новых handlers

### PrivateCore

- Policy уже описывает все job types — при добавлении handlers сверять строковые `job_type` с `ComputeJobType` enum.

---

## 5. Job types из `compute_job_policy` (справочник)

Offloadable (`PREFER_WORKER` / `WORKER_ONLY`):

- `soundcloud_rpc` — **handler есть**
- `sc_artist_catalog_sync`, `sc_artist_similar_station_sync`, `sc_artist_release_sync`
- `artist_enrichment`, `track_info_fetch`, `external_import_scan`
- `track_transcoding`, `track_waveform`, `track_snippet`, `track_cover_processing`
- `track_audio_features`, `audio_embedding`, `artist_features_update`, … — `WORKER_ONLY` (уже были)

`catalog_normalize` — `LOCAL_ONLY` (исключение).

---

## 6. Известные проблемы / смешанный diff

### 6.1 Несвязанные изменения в Backend git status

В `git status` Backend много файлов **вне scope офлоада** (HLS migration, prefetch, frontend, admin catalog).  
**Не смешивать в один коммит** с офлоадом без явного запроса пользователя.

Офлоад/SC-related (ориентир для коммита):

```
app/config.py (sc_offload_*, concurrency)
app/services/sc_*.py, soundcloud_service.py, artist_catalog_sync_worker.py
app/services/compute_queue_service.py, compute_results_router.py
docker-compose.yml, .env.example
tests/app/services/test_sc_*.py, test_compute_results_router.py
```

### 6.2 `playback_streaming_policy.py` (PrivateCore)

Файл **untracked**. Backend `hls_migration.py` импортирует `HLS_MIGRATE_BATCH_SIZE`, `HLS_MIGRATE_INTER_TASK_SECONDS`.  
В untracked-файле добавлены алиасы — иначе **pytest conftest не импортируется**.  
Закоммитить в PrivateCore вместе с policy или вынести в отдельный PR.

### 6.3 Flaky test (не от этой задачи)

`tests/.../test_outbound_direct_fallback.py::test_artist_info_http_get_allows_direct_fallback` — реальный HTTP к Wikipedia; падал до изменений.

---

## 7. Команды проверки

```powershell
# Backend (из DotSoundBackend)
poetry run pytest tests/app/services/test_sc_dead_track_cache.py tests/app/services/test_sc_rpc_client.py tests/app/services/test_compute_results_router.py tests/app/services/test_compute_queue_service.py -q
poetry run ruff check app/services/sc_*.py app/services/soundcloud_service.py app/services/compute_queue_service.py app/services/compute_results_router.py

# PrivateCore
poetry run pytest tests/dotsound_private_core/services/test_sc_anti_block_policy.py tests/dotsound_private_core/services/test_compute_job_policy.py tests/dotsound_private_core/contracts/test_sc_rpc_protocol.py -q

# ComputeWorker
poetry run pytest tests/handlers/test_soundcloud_rpc.py -q
```

---

## 8. Правила для следующего агента

1. Прочитать **`AGENTS.md`**, **`TODO.md`**, `.cursor/rules/secrets-and-env.mdc`**, **`docs/ai-boundary-policy.md`**.
2. **Не читать/не трогать `.env`** без явного разрешения пользователя.
3. **PrivateCore = правила**, Backend = транспорт; новые пороги/TTL → PrivateCore.
4. `api/v1/` без прямого SQL; только services/repos.
5. Ответы пользователю — **на русском**; commit messages — **Conventional Commits на английском**.
6. Коммиты — **только по запросу** пользователя; в конце задачи дать предложения commit message **по репо**.
7. Hub: пользователь координирует через **DotSoundBackend**, но правки в 3 репо.

---

## 9. Предлагаемые commit messages (когда пользователь попросит)

```
feat(private-core): add SC anti-block policy, compute job routing, and RPC protocol
feat(backend): anti-block SoundCloud stack, dead-track cache, and optional SC RPC offload
feat(compute-worker): add soundcloud_rpc handler with per-job proxy support
```

Phase 2 (после завершения):

```
feat(backend): compute job dispatcher, reaper, and worker offload for catalog/ffmpeg jobs
feat(compute-worker): add enrichment, ffmpeg, and image compute handlers
```

---

## 10. PROMPT для новой сессии (скопировать целиком)

См. файл **`docs/handoffs/PROMPT-continue-sc-offload.md`** (готовый блок для вставки в чат).
