# Промпт: продолжить офлоад задач на ComputeWorker

Скопируй всё содержимое блока ниже в новый чат Cursor (режим Agent).

---

```
Ты продолжаешь прерванную работу в семействе репозиториев DotSound.
Хаб: C:\Users\User\PycharmProjects\DotSoundBackend
Также: C:\Users\User\PycharmProjects\DotSoundPrivateCore, C:\Users\User\PycharmProjects\DotSoundComputeWorker

ОБЯЗАТЕЛЬНО ПРОЧИТАЙ ПЕРЕД КОДОМ:
1. DotSoundBackend/docs/handoffs/2026-05-16-sc-offload-queue-optimization.md  (полный handoff)
2. DotSoundBackend/AGENTS.md
3. DotSoundBackend/TODO.md
4. .cursor/rules/secrets-and-env.mdc  — НЕ читать .env без явного ok пользователя
5. docs/ai-boundary-policy.md

КОНТЕКСТ ЗАДАЧИ
Пользователь жаловался на backlog >21k Taskiq-задач (catalog sync), 403 от SoundCloud,
sc_semaphore_timeout. Затем попросил «безумную идею»: передавать HTTP-bound и CPU-bound
задачи на DotSoundComputeWorker (отдельная машина, свой IP, proxy per job type), с умной
очередью: worker claim → success → next; fail → возврат в пул → retry → fallback на Backend.

ЧТО УЖЕ СДЕЛАНО (Phase 1 — НЕ ПЕРЕДЕЛЫВАТЬ без причины)
PrivateCore:
- sc_anti_block_policy.py, compute_job_policy.py, contracts/sc_rpc_protocol.py
- расширены outbound/profiles.py
- тесты: 67 passed на policy/rpc

Backend:
- sc_dead_track_cache.py, sc_browser_session.py, sc_rpc_client.py
- soundcloud_service.py: anti-block + SoundCloudTrackUnavailable + optional RPC offload
- artist_catalog_sync_worker.py: idempotency locks, backpressure, dead track skip
- compute_queue_service: JOB_SOUNDCLOUD_RPC, enqueue_soundcloud_rpc()
- compute_results_router: _persist_soundcloud_rpc → Redis
- config: soundcloud_global_concurrency=10, sc_offload_enabled=False (default), sc_offload_wait_seconds=30
- docker-compose: TASKIQ_MAX_ASYNC_TASKS default 50
- .env.example обновлён
- тесты sc_dead_track_cache, sc_rpc_client, compute_results_router (+sc rpc)

ComputeWorker:
- worker/handlers/soundcloud.py (handle_soundcloud_rpc)
- config: default_proxy, proxy_by_type_json
- .env.example, tests/handlers/test_soundcloud_rpc.py (6 passed)

ЧТО НЕ СДЕЛАНО — ТВОЯ ОСНОВНАЯ РАБОТА (Phase 2)
Backend:
1. app/services/compute_job_dispatcher.py — маршрутизация по compute_job_policy (offload vs local)
2. app/services/compute_job_reaper.py — expired lease → requeue / local fallback; подключить в worker startup
3. Расширить compute_results_router — persist для всех offloadable job types (catalog, enrichment, ffmpeg, cover…)
4. Local fallback handlers (используют sc_browser_session / существующие сервисы)
5. Перевести Taskiq workers на dispatcher: artist_catalog_sync_worker, artist_enrichment_worker,
   track_info_worker, external_import_worker, cover_worker, transcoding, waveform_worker, snippet_worker
6. Расширить app/api/v1/internal/compute_jobs.py — claim filter offloadable, error_kind на result, dead_track no retry
7. Добавить pytest для dispatcher/reaper/dispatcher-mode
8. ruff/black/mypy на изменённых файлах; обновить TODO.md

ComputeWorker:
1. handlers/enrichment.py, ffmpeg_jobs.py, image_jobs.py
2. backend_client.py: upload_artwork, upload_audio_variant
3. pyproject.toml: Pillow, python-magic в extra http
4. тесты stubs

ВАЖНО
- В git status Backend есть НЕСВЯЗАННЫЕ изменения (HLS migration, prefetch, frontend) — не смешивай в один коммит с офлоадом.
- compute_job_policy уже перечисляет job types — строки job_type должны совпадать с enum.
- SC_OFFLOAD_ENABLED=false по умолчанию — офлоад опционален до запуска воркера пользователем.
- Правила: PrivateCore = константы/решения; Backend = ORM/Redis/HTTP; api/v1 без select().
- Отвечай пользователю на русском. Commit messages — Conventional Commits EN, только по запросу.
- В конце дай commit message на строку для каждого затронутого репо.

ПОРЯДОК РАБОТЫ
1. Прочитай handoff-файл и перечисленные ключевые модули (compute_queue_service, compute_job_policy, soundcloud handler).
2. Реализуй dispatcher + reaper (минимально рабочий vertical slice).
3. Подключи один Taskiq worker (например catalog sync) к dispatcher end-to-end.
4. Расширяй на остальные job types и ComputeWorker handlers.
5. Прогони тесты и lint; обнови TODO.md.

Начни с чтения handoff и краткого плана из 5–7 пунктов, затем приступай к compute_job_dispatcher.py.
```

---
