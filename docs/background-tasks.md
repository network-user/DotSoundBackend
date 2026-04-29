# Background tasks: unified layer

Practical guide for adding, scheduling and monitoring background
work in DotSoundBackend. Goal: every new task plugs into the same
reliability layer (retries, dead-letter, idempotency, admin
visibility) without bespoke plumbing.

## Two channels (intentional)

We deliberately keep **two separate transports** for background
work:

1. **Taskiq + Redis** — in-process Backend tasks (transcode, cover,
   waveform, search reindex, lyrics dispatch, enrichment, admin
   alerts). Brokered by `app.core.tkq.broker`.
2. **HTTP-pull with HMAC** — DotSoundComputeWorker tasks
   (audio analysis, similarity indices, ASR). Persisted as
   `ComputeJob` / `LyricsJob` rows; worker claims via
   `/api/v1/internal/audio-compute/...` and `/internal/compute/...`.

The two channels are not unified at the transport level — they have
different operational profiles. They **are** unified at the admin
panel level: `GET /api/v1/admin/tasks/overview` shows queue depths,
`BackgroundJob` status counts, `ComputeJob`/`LyricsJob` counts and
upcoming schedules in one response.

## Three job tracking tables

| Table             | Channel        | Created via                         |
|-------------------|----------------|-------------------------------------|
| `background_jobs` | Taskiq         | `app.services.background_jobs.enqueue()` |
| `compute_jobs`    | HTTP-pull      | `app.services.compute_queue_service` |
| `lyrics_jobs`     | HTTP-pull      | lyrics dispatch path                 |

Existing 16 Taskiq workers still call `task.kiq(...)` directly and
do **not** create a `BackgroundJob` row. They will migrate to
`enqueue()` incrementally. **All new Taskiq-backed work must go
through `enqueue()`** so it appears in the unified admin view and
benefits from retry/dead-letter.

## Adding a new background task

### 1. Define the task (Taskiq side)

```python
# app/services/playlist_worker.py
import structlog
from app.core.tkq import broker

logger = structlog.get_logger(__name__)

@broker.task(task_name="playlist.generate_for_user")
async def generate_playlist_for_user_task(
    user_id: int, seed: str | None = None
) -> dict:
    # do work — keep idempotent if you can
    return {"user_id": user_id, "seed": seed, "ok": True}
```

Register the module in `main.py` (the list passed to the Taskiq
worker subprocess).

### 2. Enqueue through the wrapper

```python
from app.services.background_jobs import (
    IdempotencySkipped,
    enqueue,
)
from app.services.playlist_worker import (
    generate_playlist_for_user_task,
)

try:
    job_id = await enqueue(
        generate_playlist_for_user_task,
        payload={"user_id": user.id, "seed": "weekly"},
        queue="default",
        max_attempts=3,
        idempotency_key=f"playlist:weekly:{user.id}",
        idempotency_ttl_seconds=600,
    )
except IdempotencySkipped:
    job_id = None  # already queued in this window
```

The wrapper inserts a `BackgroundJob` row (status `queued`),
attaches the row id as a Taskiq label, then kicks the task. The
lifecycle middleware (`app/core/taskiq_middleware.py`) updates the
row to `running` / `done` / `failed_terminal` automatically.

### 3. Make long-running work cancellable

Inside the task, periodically check the cancel signal:

```python
from app.services.cancellation import is_cancelled

if await is_cancelled(job_id):
    logger.info("playlist_cancelled_by_admin", job_id=job_id)
    return {"cancelled": True}
```

`POST /api/v1/admin/tasks/jobs/{id}/cancel` flips status to
`cancelling` and sets the Redis cancel key picked up by this check.

## Adding a periodic schedule

Schedules live in the `scheduled_jobs` table and are evaluated by
`app.services.scheduler_service` (one leader instance held via a
Redis lock).

Either via admin API:

```
POST /api/v1/admin/tasks/schedules
{
  "name": "weekly_playlist_refresh",
  "task_name": "playlist.generate_for_user",
  "cron": "0 4 * * 1",
  "queue": "default",
  "payload": {"seed": "weekly"},
  "enabled": true
}
```

Or by adding a row in an Alembic migration (recommended for
defaults that ship with the codebase).

`run-now` for ad-hoc kicks: `POST /tasks/schedules/{id}/run-now`.

### Cron vs orchestrator

There are two distinct patterns. **Do not** mix them.

- **Scheduled (cron)** — short, fire-and-forget kicks at known
  intervals. Use `ScheduledJob` rows.
- **Orchestrator** — long-running dispatcher loop with custom
  pacing/fan-out (e.g. `import_queue_dispatcher`,
  `lyrics_global_orchestrator`). Stays as a hand-written
  `asyncio` loop registered on `WORKER_STARTUP`. Don't try to
  express continuous orchestrators as cron rows.

## Admin panel endpoints

All under `/api/v1/admin/tasks/` and gated by
`tasks.manage` / `tasks.run` capabilities (`require_step_up` for
mutating actions).

| Method | Path                              | Purpose                              |
|--------|-----------------------------------|--------------------------------------|
| GET    | `/queues`                         | Taskiq queue depths (Redis LLEN)     |
| GET    | `/overview`                       | Single-pane summary                  |
| GET    | `/jobs`                           | Paginated `BackgroundJob` listing    |
| GET    | `/jobs/{id}`                      | Detailed view                        |
| POST   | `/jobs/{id}/cancel`               | Signal cancel + flip status          |
| POST   | `/jobs/{id}/retry`                | Re-enqueue with new row              |
| GET    | `/lyrics-jobs`, `/compute-jobs`   | Pull-channel listings (legacy)       |
| GET    | `/schedules`                      | List schedules                       |
| POST   | `/schedules`                      | Create schedule                      |
| PATCH  | `/schedules/{id}`                 | Update schedule                      |
| DELETE | `/schedules/{id}`                 | Remove schedule                      |
| POST   | `/schedules/{id}/run-now`         | Manual immediate kick                |
| POST   | `/run/{task_name}`                | Manual kick from a whitelist         |

## Retry and dead-letter

`BackgroundJobLifecycleMiddleware` reads `bgjob_id` and
`bgjob_max_attempts` from the message labels.

- On exception, if `attempts < max_attempts`: row status → `queued`,
  task is re-kicked after `min(60, 2^(attempts-1))` seconds with
  the same labels (so retries reuse the same `BackgroundJob` row).
- On exception when retries are exhausted: row status →
  `failed_terminal`, an `admin.alert.send` task is fired with
  `event_type=background_job.failed_terminal`.

Tasks kicked the legacy way (`task.kiq(...)` without `enqueue()`)
have no `bgjob_id` label and are passed through untouched — no DB
writes, no managed retries. This preserves backwards compatibility
during incremental migration of the existing 16 workers.

## Queues (forward-looking)

Right now there is one `taskiq:*` queue. The `BackgroundJob.queue`
column already records intent (`default | media | enrichment |
scheduler`) so we can split brokers later — separate
`ListQueueBroker` instances bound to different `queue_name`s and
different worker pools — without changing call sites.

## Local end-to-end check

1. Run migrations: `alembic upgrade head` (creates
   `background_jobs`, `scheduled_jobs`).
2. Start the stack: `python main.py`.
3. `GET /api/v1/admin/tasks/overview` — should return zero
   background jobs.
4. Create a schedule:
   ```
   POST /api/v1/admin/tasks/schedules
   {"name":"smoke","task_name":"admin.alert.send","cron":"*/2 * * * *","payload":{"event_type":"smoke","severity":"info","title":"smoke","details":"ok","user_id":null,"ip":null,"ua":null}}
   ```
5. Wait two minutes — a new `BackgroundJob` row appears with
   `scheduled_job_id` set, status flips through
   `queued → running → done`.
6. Manually fail a task three times to verify dead-letter
   (`status=failed_terminal` + admin alert).
