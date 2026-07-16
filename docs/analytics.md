# Аналитика (self-hosted Umami)

Mini App `.звук` шлёт обезличенную веб-аналитику в тот же self-hosted
**Umami**, что и портфолио (DotBioSite) и DotLearn. Umami cookieless, без
персональных данных и баннера согласия.

## Как это устроено

- Контейнер `umami` живёт в общей docker-сети `dotsound` (сам стек
  Umami + Postgres поднимается в `DotBioSite/deploy/analytics`, здесь он
  не дублируется). Дашборд открывается на отдельном поддомене
  `{$ANALYTICS_DOMAIN}` через фронт-Caddy (`Caddyfile`).
- Трекер отдаётся **first-party** с домена самого сайта по пути `/stats/*`,
  а не с поддомена аналитики. Это не ослабляет CSP (`script-src`/`connect-src`
  остаются `'self'`) и реже попадает под ad-block. За проксирование отвечает
  `frontend/nginx.conf`:
  - `GET /stats/script.js` → `umami:3000/script.js` (сам трекер);
  - `POST /stats/api/send` → `umami:3000/api/send` (события).
- Тег `<script defer src="/stats/script.js" data-website-id="…">`
  инъектится в `<head>` **на этапе сборки** Vite-плагином `dotsound:umami`
  (`frontend/vite.config.ts`), и только если задан `VITE_UMAMI_WEBSITE_ID`.
  Без ключа (dev, локальная сборка, CI без переменной) трекер не грузится.
- Pageview'ы (включая переходы между экранами SPA/React Router) трекаются
  автоматически — дополнительный JS не нужен.

### Переменные сборки фронтенда

Vite инлайнит их в бандл на этапе `npm run build`, поэтому они нужны
**во время сборки образа**, а не в рантайме.

| Переменная               | Обязательна | Назначение                                                                 |
|--------------------------|-------------|----------------------------------------------------------------------------|
| `VITE_UMAMI_WEBSITE_ID`  | да          | Public website id (UUID) из дашборда Umami. Виден в HTML — это не секрет.   |
| `VITE_SITE_URL`          | желательно  | Публичный origin сайта, напр. `https://твой-домен`. Даёт `data-host-url`/`data-domains` (события шлются только с прод-домена). |
| `VITE_UMAMI_SRC`         | нет         | Путь к трекеру, по умолчанию `/stats/script.js`. Менять не нужно.           |

Если `VITE_SITE_URL` не задан, трекер всё равно работает (события уходят на
`/stats/api/send` того же origin), просто без ограничения `data-domains`.

## Подключение — по шагам

### 1. Зарегистрировать сайт в дашборде Umami

1. Открой дашборд Umami: `https://{ANALYTICS_DOMAIN}` (поддомен из `.env`,
   тот же логин, что и для портфолио).
2. **Settings → Websites → Add website**.
3. Name: `.звук`; Domain: домен Mini App (значение `DOMAIN` из `.env`, без
   `https://`).
4. Сохрани и открой у сайта **Edit** → скопируй **Website ID** (UUID).

### 2. Прописать website id для CI-сборки

Основной прод-образ фронта собирает CI и кладёт в GHCR (сервер его тянет).
Значит переменные нужны в GitHub Actions как **Repository Variables** (не
секреты — id публичный):

1. GitHub → репозиторий → **Settings → Secrets and variables → Actions →
   вкладка Variables → New repository variable**.
2. Добавь:
   - `VITE_UMAMI_WEBSITE_ID` = скопированный UUID;
   - `VITE_SITE_URL` = `https://твой-домен` (тот же, что `DOMAIN`).

Workflow `.github/workflows/deploy.yml` уже прокидывает их в
`docker build` фронта.

### 3. (Опционально) продублировать в серверный `.env`

Нужно только для запасного пути: если CI-образ не скачался, `deploy.sh`
собирает фронт прямо на сервере через `docker compose build`, который берёт
`args` из `.env`. Чтобы трекер запёкся и в этом случае, добавь в серверный
`DotSoundBackend/.env`:

```dotenv
VITE_UMAMI_WEBSITE_ID=<UUID-из-Umami>
VITE_SITE_URL=https://твой-домен
```

> `.env` не в git — правь его прямо на сервере. В шаблон `.env.example`
> можно добавить эти же строки с пустыми значениями как подсказку.

### 4. Задеплоить

Пуш в `main` (или `workflow_dispatch`) → CI пересоберёт образ фронта с
зашитым website id → `deploy.sh full` подтянет и поднимет его.

### 5. Проверить

1. Открой Mini App в браузере (не только в Telegram — чтобы видеть DevTools).
2. **Network**:
   - `GET /stats/script.js` → `200`;
   - при навигации `POST /stats/api/send` → `200`/`204`.
3. В дашборде Umami у сайта `.звук` появятся визиты (обычно в течение минуты).

Если `/stats/script.js` отдаёт `404` — образ собран без `VITE_UMAMI_WEBSITE_ID`
(проверь repo variable / пересобери). Если `502`/`503` — контейнер `umami`
не поднят или не в сети `dotsound`.

## Кастомные события (на будущее)

Базовые pageview'ы уже трекаются. Для клика по кнопке достаточно
data-атрибута, без JS:

```html
<button data-umami-event="play-track" data-umami-event-track-id="123">▶</button>
```
