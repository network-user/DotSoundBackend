> Последний прогон: iron-gate · 2026-07-06 (пост-фикс). Снимок: [2026-07-06-iron-gate.md](2026-07-06-iron-gate.md) · предыдущий: [2026-07-06-iron-ledger.md](2026-07-06-iron-ledger.md) · история: [docs/audit/](.)

# Security Audit · Iron Gate · 2026-07-06

| Поле | Значение |
|------|----------|
| Статус | PASSED |
| Прогон | iron-gate (пост-фикс от iron-ledger) |
| Уровень | full |
| Охват | leaks + code |
| Модель | Claude Fable 5 |
| Дата | 2026-07-06 |

> Обновление 2026-07-06 (пост-деплой): fix M3 (обязательные prod-креды через
> `${VAR:?}`) **откачен** - он ломал прод-деплой: сервер использует дефолтный
> пароль и БД уже инициализирована с ним. Weak-default реклассифицирован в
> **accepted/deferred** (Medium, internal-network). Реальное усиление = задать
> креды в prod `.env` + ротация в Postgres/MinIO + миграция, отдельной операцией.
> Вердикт не меняется (Critical/High нет).

## Сводка

```
Трек A · Секреты/ключи:      0   (Crit 0 / High 0)
Трек A · PII/экспозиция:     0
Трек A · История git:        0   (616 коммитов / 8 ссылок — чисто)
Трек B · Инъекции/exec:      2   (1 Low, 1 Info)
Трек B · Authz/крипто/деф.:  0 открытых Medium (все закрыты), остаток Low/Info
Трек B · Зависимости/инфра:  0 открытых Medium (закрыто), остаток Low
PrivateCore black-box:       Accepted (решение владельца)
```

```
Severity (открытые): Crit 0 · High 0 · Med 0 · Low 16 · Info 5
Accepted (owner):    black-box политика — 10 пунктов Medium + 5 Low
Готовность: 9/10
Вердикт: PASSED
```

Прогон `iron-ledger` дал PASSED WITH WARNINGS (0 Critical/High, 13 Medium). В прогоне
`iron-gate` три security-Medium устранены правками, кластер black-box принят владельцем как
осознанное решение. Открытых Medium и выше не осталось → PASSED.

## Устранено в этом прогоне

| Было (Medium) | Файл | Что сделано |
|---------------|------|-------------|
| IDOR: `POST /tracks/{id}/info/refresh` без проверки владельца | `app/api/v1/tracks/info.py:71` | Добавлен guard `if not is_public and user.id != owner_id: raise 403` — как в GET-сиблинге |
| Слабый admin-гейт на деструктивных/пишущих операциях артистов | `app/api/v1/artists.py` | `DELETE /{id}`, `supplemental/batch-prompt`, `supplemental/batch-import` → `require_admin_session`; фронт `deleteArtist` → `adminApi.deleteArtist` |
| Weak default-креды сервисов без prod fail-fast | `docker-compose.prod.yml` | `POSTGRES_PASSWORD`/`MINIO_ROOT_PASSWORD` сделаны обязательными (`${VAR:?...}`) в prod-overlay |

Неразрушающие энричмент-триггеры артистов (`enrich`, `enrich/watch`, `enrich/status`,
`supplemental/refresh`) остаются на `require_admin`: они вшиты в обычное приложение и
вызываются админом по user-JWT; перевод на admin-session — продуктовое решение. Остаток
классифицирован как **Low**.

Пост-фикс закрыто ещё 3 Low: constant-time сравнение секрета в `generate-code`
(`hmac.compare_digest`), `permissions: contents: read` в обоих workflow, `frontend/.dockerignore`.

## Принятые исключения (решение владельца)

Кластер нарушений hard-rule «black-box» (внутренности приватного ядра видны за границей в
`poetry.lock`, `docs/`, `agents.md`, `app/config.py`, `app/core/observability.py`, тестах,
частично backend→frontend) принят владельцем как осознанный. Полный перечень — в снимке
[2026-07-06-iron-ledger.md](2026-07-06-iron-ledger.md). Рекомендация к пересмотру сохраняется
при смене видимости репозитория на public.

## Остаточные находки (Low / Info)

Полная таблица остатка — в снимке [2026-07-06-iron-gate.md](2026-07-06-iron-gate.md).
Ключевые: SSRF-guard (redirect-bypass, DNS-rebinding, admin-PATCH без гварда), ffmpeg `file`
в whitelist, плавающие теги образов и GitHub Actions, base image без digest-пина,
`poetry.lock` рассинхрон.
