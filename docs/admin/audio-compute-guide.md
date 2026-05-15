# Compute & Lyrics Cascade — Admin Guide

Гайд для администратора DotSound по работе с разделом
**Compute** в админ-панели (`/admin/audio-compute`).

> Все экраны рендерит [`frontend/src/admin/routes/AudioComputeRoute.tsx`](../../frontend/src/admin/routes/AudioComputeRoute.tsx). Технический контракт для воркеров — в [`compute-worker-protocol.md`](../compute-worker-protocol.md).

---

## 1. Что вы здесь видите

Сверху вниз страница состоит из 8 секций:

1. **How to add a worker** — встроенная пошаговая инструкция с
   копируемыми сниппетами. Сворачивается в одну строку, когда
   у вас уже есть хотя бы один воркер. Можно открыть назад
   кнопкой **Show**.
2. **Routing mode** — глобальный переключатель всего
   lyrics-конвейера:
   - `auto` — нормальный режим, работает каскад.
   - `force_local_cpu` — игнорирует remote workers, использует
     только catalog tier (legacy: ничего не считает).
   - `force_remote_gpu` — игнорирует catalog, ставит всё в
     очередь для воркеров. Если воркер не подключится в течение
     `lyrics.max_queue_time_s` — job фейлится.
   - `disabled` — вообще не пропускает новые задания
     (`/lyrics/auto-generate` вернёт 503).
3. **Cascade order** — порядок tier'ов и набор активных. По
   умолчанию `catalog_only` → `remote_whisper` → `speechkit_paid`.
   Кнопками `↑/↓` меняете очередь, `Remove` исключаете tier,
   `Save cascade` фиксируете в БД (запись попадает в
   `app_settings` под ключом `lyrics.cascade_order`,
   распространяется через Redis cache за ~30 сек). Предупреждение:
   изменение порядка относится к **новым** job'ам — те, что уже
   в полёте, доезжают по своему сохранённому каскаду из
   `LyricsJob.tiers_planned`.
4. **SpeechKit (paid tier)** — статус Yandex SpeechKit:
   включён/выключен, бюджет на месяц, потрачено, остаток, тариф,
   per-job soft limit, наличие API-ключа. Кнопка **Reset month
   spent counter** обнуляет Redis-счётчик (использовать только
   если вы уверены — это влияет на гард в реальном времени).
5. **Workers** — форма создания + таблица.
6. **Jobs** — таблица LyricsJob: сортировка «как в очереди»
   (queued/running сверху, затем по `queue_priority`) или «сначала
   новые»; колонка **Queue routing** (приоритет, pin на воркера,
   **Apply**); для `running` с активным pull — переназначение
   снимает lease и возвращает job в `queued` (старый воркер
   получит 404 на result — это норма).
7. **Generic compute jobs** — очередь `compute_jobs`, которую
   тянет тот же DotSoundComputeWorker по `/internal/compute`
   (типы вроде audio features / similarity). Там же priority,
   pin и опционально **Release lease** для зависших `claimed`.
8. **Worker audit (last 200)** — лог действий, фильтр по action.

Ниже идут отдельные подсказки по каждому workflow.

---

## 2. Как добавить первого воркера

1. Прочитайте **How to add a worker** наверху страницы — там
   все команды с кнопками **Copy**.
2. На второй машине (или локально) сделайте `git clone` репо
   `DotSoundComputeWorker` и `poetry install --with cpu,dev`
   (или `gpu,demucs,dev`).
3. На этой странице в секции **Workers**:
   - Введите имя (`local-dev`, `vps-eu-1`, любое читаемое).
   - Profile: **`gpu_full`** для tier'а `remote_whisper`.
   - **Allowed IP CIDRs** — нажмите один из пресетов:
     - **Localhost only** — если воркер на той же машине.
     - **Private LAN** — если в одной локалке/VPC.
     - **Single VPS IP** — отредактируйте под ваш публичный IP
       (рекомендуется для prod).
     - **Allow any (RISKY)** — только если egress контролировать
       никак не получается. Включит чек-бокс «I accept the risk»,
       без него Backend вернёт 400.
   - `max_concurrent_jobs` — оставьте `1` пока не уверены, что
     железо тянет больше.
4. Нажмите **Create worker**. Появится карточка с
   `WORKER_SECRET` — скопируйте сразу. **Второй раз он показан не
   будет.**
5. Положите `WORKER_ID`, `WORKER_SECRET` и `WORKER_BACKEND_BASE_URL`
   в файл `DotSoundComputeWorker/.env` на удалённой машине.
6. Запустите воркер: `make dev` или systemd-юнит из
   onboarding-инструкции.
7. В таблице Workers через ~15 сек должна появиться зелёная
   точка `active` напротив воркера, обновится `last_seen` и
   `IP`.

Если что-то не загорается зелёным — кликните **Open** на воркере,
откроется детальный drawer с последними событиями. Самые частые
причины:

| Action в audit | Что значит | Что делать |
|---|---|---|
| `auth_fail` reason=`bad_signature` | Секрет в .env не совпадает с тем, что в БД | Rotate secret и обновите .env |
| `auth_fail` reason=`stale_timestamp` | Часы воркера и Backend разъехались | Поправить системное время / NTP |
| `auth_fail` reason=`ip_not_allowed` | IP воркера не в его персональном allowlist | В drawer'е → **Edit** → добавьте текущий IP |
| `auth_fail` reason=`nonce_replay` | Воркер посылает один и тот же nonce | Перезапустить воркер; если повторяется — вероятен MITM |
| HTTP 404 на `/internal/...` | IP не в **глобальном** allowlist | Добавить CIDR в `INTERNAL_API_ALLOWED_CIDRS` в `.env` Backend |
| HTTP 404 + `internal_api_ip_blocked` `ip=172.x.x.x` | Backend видит docker IP контейнера | Для compose-worker нужен docker bridge CIDR (`172.16.0.0/12`); для remote-worker проверьте `TRUSTED_PROXY_CIDRS` / `INTERNAL_API_TRUSTED_PROXIES` и публичный egress CIDR |
| `rate_limit_exceeded` | Воркер шлёт слишком часто | Проверить `WORKER_HEARTBEAT_INTERVAL_SECONDS` (должен быть ≥5) |

---

## 3. Открыть детали воркера

Кликните **Open** в строке воркера → справа выезжает
**Worker drawer**:

- Полный паспорт: id, profile, allowed profiles, concurrency,
  CIDRs, last seen, last IP, создан когда.
- **Edit** рядом с CIDRs — inline редактирование без модалки.
- **.env snippet** — копируется одной кнопкой (без секрета —
  его всё равно надо знать заранее).
- **Recent events** — последние 100 событий из Redis Stream
  `worker_events:{id}`. Пока drawer открыт, список также
  подписывается на admin WebSocket (`worker_logs` + `worker_id`)
  с быстрым циклом на сервере; при отсутствии WS остаётся
  периодический REST‑снимок (каждые 5 с). Каждое событие
  имеет цветной pill: green = ок, yellow = warn, red = проблема.
- **Claim pause / drain** — мягкая пауза: Backend перестаёт
  выдавать новые lease на lyrics ASR и на generic compute для
  этого воркера до `claims_paused_until` или до **Resume claims**.
  Отмена running lyrics job из админки ставит токен в heartbeat
  (`cancel_job_ids`), чтобы воркер по возможности остановился
  между стадиями пайплайна.
- **Package version** — из заголовка `X-Worker-Package-Version`
  на heartbeat; опциональный пол `COMPUTE_WORKER_MIN_PACKAGE_VERSION`
  в `.env` Backend добавляет в ответ флаг «ниже минимума».
- **Dangerous actions:**
  - **Rotate secret** — двухшаговое подтверждение.
    После rotate'а старый секрет мгновенно невалиден,
    nonce-кэш для воркера чистится, новый секрет показан раз.
  - **Revoke worker** — двухшаговое подтверждение. Воркер
    сразу `revoked_at`, его in-flight jobs автоматически
    переходят на следующий tier через cascade-fallback,
    nonce-кэш чистится. Восстановить нельзя — только создать
    нового воркера.

> Step-up TOTP: оба dangerous-действия попадают в
> `ADMIN_DANGEROUS_ACTIONS` PrivateCore — если у вашего
> админ-пользователя включён step-up, перед подтверждением
> попросят TOTP-код.

---

## 4. Управление каскадом

В секции **Cascade order**:

- Стрелками `↑/↓` меняете порядок. Изменения копятся в
  pending-state — внизу появятся кнопки **Save cascade /
  Discard**. Backend инвалидирует кэш сразу после Save.
- Кнопкой **Remove** уберёте tier из каскада (например, если
  не хотите Backend-side catalog поиск, а хотите сразу
  remote_whisper).
- Под кнопкой `+ catalog_only` (и т.п.) добавляете tier
  обратно.

Что происходит, если вы случайно убрали все tier'ы и сохранили?
PrivateCore-валидатор `normalize_cascade` вернёт DEFAULT_CASCADE
из трёх стандартных tier'ов — пустого списка не будет.

---

## 5. Управление SpeechKit (платный fallback)

Tier выключен по умолчанию. Что нужно для включения:

1. В [.env Backend](../../.env) проставить:
   ```
   YANDEX_SPEECHKIT_ENABLED=true
   YANDEX_SPEECHKIT_API_KEY=<ваш api key>
   YANDEX_SPEECHKIT_FOLDER_ID=<folder>
   YANDEX_SPEECHKIT_MONTHLY_BUDGET_RUB=500
   YANDEX_SPEECHKIT_RATE_RUB_PER_MINUTE=16
   YANDEX_SPEECHKIT_SOFT_PER_JOB_LIMIT_RUB=10
   ```
2. Перезапустить Backend.
3. В разделе **SpeechKit** на этой странице должно быть:
   - Status: green pill `enabled`
   - api key missing — отсутствует, если ключ задан
   - Бюджет: `0.00 / 500.00 ₽`, остаток `500.00 ₽`
4. (Юридически) Обновить `LEGAL.md`, `PRIVACY_POLICY.md` и
   `USER_AGREEMENT.md` с упоминанием передачи аудио в Yandex
   Cloud — см. раздел "Cross-border data transfer" в LEGAL.md.

В работе:

- Каждый успешный SpeechKit-запрос списывает с месячного
  счётчика `speechkit_spent_rub_total` в Prometheus и в Redis.
- Если подойдёте к бюджету — следующий job получит
  `speechkit_budget_exhausted` в `tier_attempts`, cascade
  пропустит tier и закроет job как failed.
- Soft per-job limit (по умолчанию `10₽`) защищает от
  случайной отправки длинных аудио. Если хотите однократно
  превысить — отправляйте через API с `force_paid=true`
  (admin-only флаг, в UI пока не вынесен).
- **Reset month spent counter** — крайнее средство. Очищает
  Redis-ключ `speechkit_spent:YYYYMM`. Полезно если хотите
  тестировать вне сезонной квоты, в проде — не нажимайте без
  очень веской причины.

---

## 6. Мониторинг job'ов

Секция **Jobs** показывает последние 200 LyricsJob'ов с
колонками:

- **ID** — короткий префикс `lj_xxxx`.
- **Track** — track_id.
- **Status** — `queued / running / done / failed / error`.
- **Tier** — текущий активный tier (`catalog_only`,
  `remote_whisper`, `speechkit_paid`).
- **Attempts** — сколько tier'ов уже пробовали (счётчик с
  тултипом, который показывает каждую попытку с её ошибкой).
- **Worker** — кто claim'ил (если remote_whisper).
- **Duration** — суммарное время.
- **Trace** — открывает inline-секцию с полным таймлайном
  всех попыток tier'ов: timestamp, статус (success / fail /
  miss / gated / queued), причина ошибки.

Используйте **Trace** когда пользователь жалуется "лирика не
сгенерировалась" — за 5 секунд видно на каком tier'е и почему
застряла.

### Очередь, приоритет и pin (LyricsJob)

- Поле **`queue_priority`** (целое, в разумных пределах): при
  claim среди `queued` сначала берутся большие значения, затем
  старые по `created_at`.
- **`pinned_worker_id`**: пока задано, job увидит в claim только
  этот воркер (профиль воркера должен совпадать с `LyricsJob.profile`,
  с учётом пары `remote_whisper` / `gpu_full`). После успешного
  claim pin сбрасывается.
- API: `PATCH /api/v1/admin/audio-compute/jobs/{id}/routing`
  (`audio_compute.manage`). В аудите: `admin_job_routing`.

### Generic compute queue (`compute_jobs`)

Та же страница показывает хвост очереди internal/compute.
Поле **`priority`** уже использовалось при claim; добавлен
**`pinned_worker_id`** по той же идее, что и для lyrics.
**Release lease** переводит `claimed` обратно в `pending` без
ожидания истечения дедлайна. API:
`PATCH .../audio-compute/generic-compute-jobs/{id}/routing`.
Аудит: `admin_compute_job_routing`.

### Расшифровка: `cascade exhausted: …` в прогрессе (Lyrics / DevTools)

Сообщение в UI — это
`"cascade exhausted: " + последняя_ошибка_тирa` (см.
`app/services/lyrics_cascade.py`, `_advance_to_next_tier`). Последняя
ошибка — это причина **последнего** отклонения тира (`_dispatch_to_tier`
или шаг `handle_tier_failure` перед сменой тира), пока `select_next_tier`
ещё не вернул `null`.

| Хвост в лог-лайне | Что значит |
|-------------------|------------|
| `no_track_audio` | Для `remote_whisper` / `speechkit_paid` на треке **нет** ни S3-`file_key`, ни `sc_url` (для ASR в каскаде нужен хотя бы один источник; SoundCloud-импорт обычно даёт `sc_url`). |
| `speechkit_disabled` | Дошли до `speechkit_paid`, но `should_use_paid_asr` вернул отказ (Yandex SpeechKit выключен в настройках, нет ключа, и т.п.). **Не путать** с «нет аудио»: сначала проходит гейт наличия аудио, потом бюджет/включение. |
| `speechkit_no_budget` / `…budget_exhausted` | Аналогично, бюджет/лимит. |

**Почему в логах бывает `no_track_audio`, а в UI в другом прогоне —
`speechkit_disabled`:** в одном прогоне последний отклонённый тир
закончился на «нет аудио», в другом — ветка дошла до проверки SpeechKit
(например после деплоя с `sc_url` / с другим `track_id`). Смотрите
**Trace** в админке по `job_id` и `scripts/inspect_track.py
<track_id>` (репо Backend) для строки `tracks` в БД.

---

## 7. Аудит и расследования

**Worker audit (last 200)** — единый лог всех событий
worker'ов: heartbeat, claim, progress, result, fail, auth_fail,
rate_limit_exceeded, anomaly, auto_suspend, ott_fail,
audio_sha_mismatch, result_invalid, admin_job_routing,
admin_compute_job_routing.

Используйте **Filter** для расследований:

| Сценарий | Что выбрать |
|---|---|
| Кто-то долбит API и пытается фейкать секрет | `auth_fail` |
| Воркер уехал в auto-suspend, понять почему | `auto_suspend` + `anomaly` |
| Подозрение что воркер фейкает результаты | `anomaly` (см. meta.anomaly_type) |
| Не доходят jobs | `claim_empty` подряд + `rate_limit_exceeded` |
| Воркер скачал чужое аудио? | `ott_fail` (чужой IP пытался выкупить OTT) |

`Meta` показывает обрезанный JSON c полным контекстом
(детали аномалии, лимиты, причины). Полная запись —
в БД `worker_audit_log`.

Retention: 90 дней. Старые записи режет ежедневный
`audit_log_pruner_task`.

---

## 8. Что делать при инцидентах

### Воркер ушёл в auto-suspend

Найдите его в таблице — будет жёлтый pill `suspended until ...`.
Откройте drawer:

1. Посмотрите Recent events — там будет `auto_suspend` с meta:
   `trigger=anomaly_threshold` или `trigger=rate_limit_strikes`.
2. Если `rate_limit_strikes` — вероятно баг в воркере,
   слишком частые запросы. Решение: исправить интервалы в
   `.env` воркера, дождаться окончания suspend'а.
3. Если `anomaly_threshold` — что-то сильно странное в
   результатах. Посмотрите meta'у первого `anomaly` события.
   Самое подозрительное: `duplicate_result` (воркер
   возвращает одинаковую лирику для разных треков →
   возможно скомпрометирован, **немедленно Revoke**).

### Подозрение на утечку секрета

1. Откройте drawer воркера → **Rotate secret**.
2. Сразу `confirm rotate`. Появится новый секрет (один раз).
3. Положите новый секрет в `.env` воркера, перезапустите его.
4. Старый секрет уже невалиден, любые запросы с ним → 401.
5. Если есть ощущение что воркер в принципе вне доверия —
   вместо rotate сделайте **Revoke worker** и создайте нового.

### Виральная нагрузка → SpeechKit рискует выесть бюджет

1. Зайдите в секцию **SpeechKit**, проверьте `Spent / Budget`.
2. Если близко к лимиту — поменяйте `Routing mode` на
   `force_local_cpu` (cascade всё равно включит catalog tier,
   но remote и speechkit пропустит). Это сразу останавливает
   расходы.
3. Или временно снизьте бюджет в `.env` Backend и перезапустите.
4. Когда волна спадёт — верните routing mode на `auto`.

### Backend перегружен входящими job'ами

1. Routing mode → `force_remote_gpu`. Это перестанет
   обрабатывать catalog tier на Backend (catalog довольно
   лёгкий, но всё-таки I/O).
2. Поднимите дополнительный воркер (Add worker → запустите на
   ещё одной машине).
3. Когда стабилизируется — верните на `auto`.

---

## 9. Capability-матрица

| Capability | Что разрешает |
|---|---|
| `audio_compute.manage` | Видеть workers/jobs, создавать, ревокать |
| `audio_compute.rotate_secret` | Ротировать секреты (отдельно от manage) |
| `audio_compute.update_allowlist` | Менять CIDRs существующих воркеров |
| `audio_compute.view_audit` | Видеть audit-таблицу |
| `lyrics.routing` | Менять routing mode, cascade order, SpeechKit |

Раздавайте через `scripts/bootstrap_admin.py`:

```powershell
poetry run python scripts/bootstrap_admin.py `
  --email admin@example.com `
  --capabilities `
  audio_compute.manage,audio_compute.rotate_secret,audio_compute.update_allowlist,audio_compute.view_audit,lyrics.routing
```

---

## 10. Дальше

- Контракт HMAC + claim/result для самописного воркера —
  [`docs/compute-worker-protocol.md`](../compute-worker-protocol.md).
- Полная архитектура каскада — [`docs/project_context.md`](../project_context.md),
  раздел "Lyrics — каскадная модель".
- Threat-model и слои защиты — раздел "Security (compute pipeline)"
  в том же `project_context.md`.
- Юридические оговорки про передачу UGC во внешний API —
  [`LEGAL.md`](../../LEGAL.md), раздел
  "Cross-border data transfer".
