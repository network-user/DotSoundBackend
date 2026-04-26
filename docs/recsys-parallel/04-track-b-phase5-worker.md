# Чат B2 — Phase 5: только DotSoundComputeWorker

## Предусловия

1. В ветке **main** (или от которой ты ветвишься) уже **смержен PR из чата B1** (`03-track-b-phase5-backend.md`), либо вручную перенесён **зафиксированный контракт API** из конца файла `03-track-b-phase5-backend.md`.
2. PrivateCore с **B-pre** доступен воркеру как сейчас (path / package), без раскрытия внутренностей в логах Worker.

## Корень workspace

`C:\Users\User\PycharmProjects\DotSoundComputeWorker`

Не править в этом чате: `DotSoundBackend` (кроме чтения контракта из md), `DotSoundBot`.

## Цель

- Пакет `**worker/handlers/`** с регистром `HANDLERS[job_type]` → async обработчики; типы из B1 (audio features, artist features, similarity, catalog normalize).
- Расширение `**worker/backend_client.py`**: методы claim/result/fail/progress к **новому** base path `/api/v1/internal/compute/...` с тем же HMAC, что audio-compute (копировать схему подписи из существующего клиента).
- `**worker/main.py`:** второй asyncio-task — цикл claim для generic jobs; флаги `worker_handles_asr`, `worker_handles_compute`, `compute_concurrency_limit` в `**worker/config.py`**.
- Неизвестный `job_type` → fail с понятной причиной.
- Тесты: `tests/handlers/` или зеркало под структуру репо.

## Коммит (одна строка)

```
feat(worker): add generic compute job handlers and dual claim loop
```

(Если в вашем процессе Worker коммитят вместе с Backend одним коммитом — согласуйте; иначе отдельный коммит только в репо Worker.)

## Pytest

```
cd C:\Users\User\PycharmProjects\DotSoundComputeWorker
pytest -q tests/handlers/
```

(Добавь существующие тесты `tests/worker/test_backend_client.py` если менялся клиент.)

## Промпт для вставки в новый чат

```
Открой: C:\Users\User\PycharmProjects\DotSoundBackend\docs\recsys-parallel\04-track-b-phase5-worker.md
И контракт API из конца: docs/recsys-parallel/03-track-b-phase5-backend.md (после merge B1).
Workspace DotSoundComputeWorker. Реализуй handlers + dual-loop + config. Не называй внутренние ML-библиотеки PrivateCore в комментариях Worker. Один коммит в репо Worker.
```

## Конфликты

Параллельно с **B1 на Backend** на **разных репозиториях** — можно **только** если контракт API застыл в документе и ты готов к повторной правке после изменений B1. Безопасный режим: **B2 строго после merge B1**.

---

## После успеха всего recsys-спринта

Коммит с удалением handoff делает владелец **DotSoundBackend**: [README.md](README.md) → «Уборка» (этот файл в том каталоге).