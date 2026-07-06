# Security Audit · Iron Ledger · 2026-07-06

| Поле | Значение |
|------|----------|
| Статус | PASSED WITH WARNINGS |
| Прогон | iron-ledger |
| Уровень | full |
| Охват | leaks + code |
| Модель | Claude Fable 5 |
| Дата | 2026-07-06 |

## Сводка

```
Трек A · Секреты/ключи:      0   (Crit 0 / High 0)
Трек A · PII/экспозиция:     0
Трек A · История git:        0   (616 коммитов / 8 ссылок — чисто)
Трек B · Инъекции/exec:      2   (1 Low, 1 Info)
Трек B · Authz/крипто/деф.:  12  (2 Medium, 6 Low, 4 Info)
Трек B · Зависимости/инфра:  10  (1 Medium, 9 Low)
PrivateCore black-box:       15  (10 Medium, 5 Low)
```

```
Severity: Crit 0 · High 0 · Med 13 · Low 23 · Info 7
Готовность: 7/10
Вердикт: PASSED WITH WARNINGS
```

Секреты и утечки данных не обнаружены: рабочее дерево и вся история git (616 коммитов
по 8 ссылкам) чисты, реальных `.env`/ключей/токенов/PII нет, `.gitignore` корректен.
Рантайм-безопасность сильная: JWT HS256 с фиксированным allowlist (нет `alg=none`),
`is_admin` из БД а не из токена, Telegram-HMAC через `compare_digest`, XFF не подделывается,
ownership-проверки в service/repo слоях, secure-random для секретов, AES-GCM со свежим nonce,
security-заголовки, `verify=False` нигде, прод-валидатор конфига хардфейлит на wildcard
CORS/hosts и слабых дефолтах, backend в контейнере от non-root.

Открытых Critical/High нет — гейт пройден. Предупреждения двух видов: (1) две authz-medium
находки (IDOR на force-refresh инфо о треке и слабый admin-гейт на операциях с артистами) и
несколько hardening-low; (2) крупный кластер нарушений hard-rule «black-box» — внутренности
приватного ядра просачиваются за границу в lockfile, доках, конфиге, метриках, тестах и
пересекают backend→frontend. Это политика, не рантайм-уязвимость (severity ≤ Medium), но
подлежит устранению, особенно перед сменой видимости на public.

## Находки

| Severity | Категория | Файл:строка | Описание | Рекомендация |
|----------|-----------|-------------|----------|--------------|
| Medium | idor | app/api/v1/tracks/info.py:61 | `POST /tracks/{id}/info/refresh` не проверяет владельца/публичность (в отличие от GET-сиблинга); любой аутентифицированный читает инфо о чужом приватном треке и триггерит дорогую перегенерацию (verified) | Скопировать guard `if not is_public and user.id != owner_id: raise 403`; force-refresh — только владелец/админ |
| Medium | missing-admin-check | app/api/v1/artists.py:404 | Admin-операции incl. деструктивный `DELETE /{artist_id}` гейтятся слабым `require_admin` (обычный 7-дневный user-JWT) вместо device-pinned admin-session, как остальные 24 admin-роутера (verified: нужен украденный admin-JWT, не эскалация с нуля) | Перевести на `require_admin_session`/`require_capability`; DELETE — дополнительно `require_step_up` |
| Medium | default-credential | docker-compose.yml:18 | Weak fallback-креды сервисов (Postgres/MinIO/pgAdmin/Grafana) без обязательной prod-проверки; общая docker-сеть повышает риск латерального движения | `${VAR:?err}` или удалить `:-default` в prod overlay; fail-fast при незаданных prod-переменных |
| Medium | blackbox-leak | poetry.lock | Приватные optional-extras ядра резолвнуты в публичный lockfile — перечислен внутренний ML/outbound граф зависимостей | Ставить ядро из wheel без optional-extras в public-метаданных / регенерировать public-lock без приватного графа |
| Medium | blackbox-leak | docs/compute-worker-protocol.md:296 | Задокументированы внутренние стадии каскада, порядок фолбэков и техника выравнивания | Опаковые «internal stage» / «audio-based fallback»; порядок фолбэков держать в ядре |
| Medium | blackbox-leak | docs/compute-worker-protocol.md:326 | «Рекомендуемый стек» называет семейства/размеры/квантизацию внутренних ML-моделей | Держать reference-рецепт в отдельном ComputeWorker-репо; здесь — «audio-to-text worker» |
| Medium | blackbox-leak | docs/private-core-dependency-policy.md:64 | Полный инвентарь внутренних модулей ядра + ML-библиотеки + provider-адаптер (нарушает и собственное правило доки) | Убрать таблицу инвентаря; свести к «ядро экспонирует decision-функции» |
| Medium | blackbox-leak | agents.md:176 | Порядок тиров каскада, внешний провайдер и cost-модель + инвентарь модулей | «Internal ASR staging and cost policy (opaque)»; убрать имена провайдера и ML-библиотек |
| Medium | blackbox-leak | app/config.py:626 | Backend определяет env-переменные внешнего провайдера с бюджет/rate-порогами (принадлежат ядру) | Перенести пороги в ядро; при нужде — опаковый селектор по образцу `lyrics_provider_name` |
| Medium | blackbox-leak | app/services/compute_worker_service.py:924 | Внутреннее имя движка используется как user-facing label атрибуции — пересекает backend→frontend | Опаковый label «Audio Alignment» / «Audio-based sync» (движок не входит в 3 разрешённые атрибуции) |
| Medium | blackbox-leak | frontend/src/locales/en.json:802 | Admin worker-setup UI раскрывает движок/модель/тир каскада во frontend-бандл (и `ru.json`) | Опаковый «high-quality profile»/«internal stage»; install-инструкции — в source-available ComputeWorker-репо |
| Medium | blackbox-leak | app/core/observability.py:234 | Prometheus-метрики (`/metrics`, дашборды) раскрывают имя внешнего провайдера, его spend и переходы тиров каскада | Переименовать в опаковые метрики (`asr_paid_stage_spend_total`, `asr_stage_transitions_total`) |
| Medium | blackbox-leak | app/services/…_adapter.py:1 | Имя файла ASR-адаптера кодирует внешнего провайдера; «cascade/tier» вокабуляр протёк в backend-код и комментарии | Переименовать в provider-neutral (`asr_paid_stage_adapter.py`); в коде — «internal ASR stage» |
| Low | command-injection | app/services/lyrics_worker.py:609 | ffmpeg `-protocol_whitelist` включает `file` для удалённого HLS — вредоносный манифест мог бы читать локальные файлы (output не отдаётся атакующему) | Убрать `file`/`crypto` для удалённого HLS, оставить `http,https,tcp,tls` |
| Low | ssrf | app/services/artist_enrichment_service.py:527 | SSRF-guard обходится через 3xx-redirect: `follow_redirects=True` валидирует только начальный URL | `follow_redirects=False` + ре-валидация каждого `Location`, либо пиннинг IP |
| Low | ssrf | app/core/ssrf_guard.py:46 | Guard TOCTOU/DNS-rebinding: validate-then-connect на раздельных резолвах | Резолвить один раз, проверять IP, коннектиться на запиненный IP |
| Low | ssrf | app/repositories/track.py:689 | Admin-PATCH пишет `source_url`/`sc_url` без SSRF-guard (import-путь их гардит); playback-прокси потом фетчит | Применить `assert_public_http_url` + host-allowlist в `admin_update_track` |
| Low | cors | app/main.py:406 | `allow_credentials=True` с wildcard-capable origin — достижимо только в DEBUG (прод-валидатор блокирует) | Прод-гейт есть; правок не требуется |
| Low | exposed-port | docker-compose.observability.yml:111 | Observability-сервисы биндят 0.0.0.0 в базовом compose (prod overlay сбрасывает/loopback) | Убедиться, что prod всегда включает overlay; рассмотреть loopback и в базовом |
| Low | debug-on | app/main.py:374 | `/docs`, `/redoc`, `/openapi.json` не отключены | При прямой доступности backend-корня — `docs_url/redoc_url/openapi_url=None` в проде |
| Low | missing-step-up | app/api/v1/admin/users.py:147 | Выставление `is_admin` и hard-delete без `require_step_up` (расхождение с `users_extended`, где step-up есть) | Навесить `require_step_up`; привести гейты users.py ↔ users_extended.py в соответствие |
| Low | hmac | app/api/v1/auth.py:260 | `generate-code` сравнивает внутренний секрет через `!=` (не constant-time), рядом `internal_token` использует `compare_digest` | Заменить на `hmac.compare_digest(...)` |
| Low | docker-latest | docker-compose.yml:36 | Плавающие/mutable теги образов (`minio:latest`, `pgadmin4:latest`, `portainer-ce:latest`, `clamav:stable`) | Пин по фиксированному тегу/digest |
| Low | docker-latest | Dockerfile:5 | Backend base image `python:3.12-slim` не запинен по digest (TODO уже в комментарии файла) | Разрезолвить и запинить digest перед прод-деплоем |
| Low | ci-unpinned | .github/workflows/deploy.yml:27 | GitHub Actions на плавающих тегах, не commit-SHA (incl. `ssh-action`, получающий приватный ключ) | Пин сторонних actions по полному commit-SHA |
| Low | ci-permissions | .github/workflows/deploy.yml:9 | Нет явного `permissions:` — `GITHUB_TOKEN` наследует дефолт репо/орг | Добавить least-privilege `permissions: contents: read` |
| Low | supply-chain | docker/Dockerfile.backup:7 | `mc` качается без проверки checksum/подписи, затем `chmod +x` | Проверять запиненный sha256/подпись перед исполнением |
| Low | dockerignore | frontend/Dockerfile:14 | Нет `frontend/.dockerignore`; `COPY . .` тянет `.git`/`node_modules`/`.env` в build-контекст | Добавить `frontend/.dockerignore` (`.git`, `node_modules`, `.env*`) |
| Low | docker-socket | docker-compose.yml:441 | Portainer монтирует `docker.sock` (root-эквивалент) — profile-gated + loopback, не в дефолтном prod | Держать profile-gated/loopback; никогда не добавлять в дефолтный prod-стек |
| Low | dep-desync | poetry.lock:1 | `poetry.lock` изменён в рабочем дереве (рассинхрон с закоммиченным; образ ставит из lock) | Регенерировать/закоммитить lock, совпадающий с pyproject, до сборки |
| Low | exposed-port | docker-compose.yml:150 | Базовый compose биндит backend:8000/frontend:80 на 0.0.0.0 (prod overlay `!reset`) | Действий нет, если prod всегда base+prod overlay |
| Low | blackbox-leak | app/core/log_setup.py:28 | Лог-маршрут называет внутренний search-провайдер ядра | Ключевать по опаковому namespace (`search_provider`) |
| Low | blackbox-leak | tests/COVERAGE_NOTES.md:14 | Coverage-notes называют внутренние модули ядра и vocal-separation lib | Опаковое «external-provider and media-scraper modules omitted» |
| Low | blackbox-leak | frontend/src/admin/routes/DashboardRoute.tsx:1132 | Admin dashboard tooltip называет ML-библиотеку | «Heavy audio compute (transcription / audio processing)» |
| Low | blackbox-leak | tests/app/services/test_compute_worker_attribution.py:22 | Тест хардкодит внутреннее имя движка и тир каскада | Ассертить на опаковый label и опаковый stage-id |
| Low | blackbox-leak | app/services/lyrics_worker.py:1766 | Docstring называет in-process ASR-движок | Переформулировать в «avoids in-process ASR» |
| Info | sql | app/services/account_linking_service.py:341 | f-string интерполирует идентификаторы таблицы/колонки в `text()` — сейчас безопасно (значения из хардкод-константы) | Оставить values параметризованными; при динамике — allowlist идентификаторов |
| Info | idor | app/api/v1/users.py:446 | `GET /users/{id}/avatar` без проверки видимости профиля (share-card её делает) — только картинка | Применить ту же проверку видимости или задокументировать аватар как публичный |
| Info | idor | app/api/v1/ws.py:95 | Presence/last_seen по произвольному id без учёта visibility/block | При необходимости фильтровать через ProfileAccessService |
| Info | missing-auth | app/api/v1/search.py:81 | `/_admin/reindex` гейтится только `debug`-флагом без auth (в проде недостижимо) | Добавить `require_admin_session` даже за debug-флагом |
| Info | template | .env.example | Шаблон в индексе; `.gitignore` корректно исключает `.env.*` с `!.env.example` | Убедиться, что содержит только плейсхолдеры |

## Охват

Полный fan-out по 9 измерениям + adversarial-проверка двух ключевых authz-находок:
секреты в рабочем дереве (A1), секреты в истории git (A2), PII/machine-data (A3),
инъекции/exec (B1), authn/authz/IDOR (B2), SSRF/path-traversal/media (B3),
крипто/небезопасные дефолты (B4), инфра/CI/зависимости (B5), PrivateCore black-box (P1).
Секреты не выводились; в отчёте — `file:line` + маски. Внутренние имена приватного ядра
намеренно не тиражируются (hard-rule black-box).
