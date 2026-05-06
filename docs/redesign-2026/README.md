# DotSound Mini App — iOS Redesign 2026

Глобальный UI-редизайн фронтенда (`frontend/`) под iOS / Apple-стилистику.
Бот, бэкенд, PrivateCore и ComputeWorker — **не трогаем**.

## Зачем это

Текущий UI монохромный, минималистичный, уже частично iOS-стайл (glass-токены,
мотион-токены, View Transitions). Цель — довести его до уровня:
> «iOS 18 база + Liquid Glass из visionOS + Now Playing как Apple Music»,
> чтобы пользователь возвращался ради ощущения от приложения.

## Решения, зафиксированные владельцем (2026-05-06)

| Параметр | Значение |
|---|---|
| Цветовая система | строгий монохром (не меняем правило `docs/design-system.md`) |
| Тема | dark only |
| Шрифт | system-ui стек (SF Pro on iOS, Roboto on Android) — без лицензии |
| Анимации | `framer-motion` (полный) |
| Скоп | публичный Mini App + админка (всё кроме бота/бэкенда) |
| Стратегия | big-bang в одной ветке `redesign/ios-2026`, без feature-flag |
| Референс | iOS 18 + visionOS Liquid Glass + Apple Music Now Playing |

## Выбранные «фишки»

Liquid Glass, morph-иконки (outline ↔ filled), spring-press,
long-press context-menu, swipe-actions, ambient color от обложки,
shared-element transition, beat-pulse, Ken Burns на героях,
горизонтальные snap-карусели, Wrapped/Recap, full-screen Now Playing,
shimmer skeleton, расширенная хаптика.

## Стратегия параллельной работы

Большая работа разбита на этапы. Этап 0 — последовательный, остальные — **параллельные** в отдельных чатах. После всех — последовательный финал.

```
                            STAGE-0 (foundation)
                                    │
                                    ▼
  ┌───────┬───────┬───────┬───────┬───────┬───────┬───────┬───────┬───────┐
  ▼       ▼       ▼       ▼       ▼       ▼       ▼       ▼       ▼       │
STAGE-A STAGE-B STAGE-C STAGE-D STAGE-E STAGE-F STAGE-G STAGE-H STAGE-I    │
player  nav-auth home    library tracks  artist  admin   recap   upload   │
  │       │       │       │       │       │       │       │       │       │
  └───────┴───────┴───────┴───────┴───────┴───────┴───────┴───────┴───────┘
                                    │
                                    ▼
                            STAGE-Z (finalize)
```

Все этапы коммитят в одну ветку `redesign/ios-2026`. Конфликтов нет, потому что
каждый этап владеет **непересекающимся** набором файлов (см. SHARED-CONTRACTS).

## Файлы

| Файл | Назначение |
|---|---|
| `README.md` | этот файл, оглавление |
| `SHARED-CONTRACTS.md` | API всех общих primitives, токены, правила, no-touch list |
| `PROMPTS.md` | готовые промпты для копи-пэйст в новые чаты |
| `STAGE-0-foundation.md` | фундамент (deps, токены, primitives, App.tsx ремаунт) |
| `STAGE-A-player.md` | PlayerBar, FullscreenLyrics, NowPlayingView, QueueSheet, Equalizer |
| `STAGE-B-nav-auth.md` | BottomNav, Onboarding, Auth, BannedScreen |
| `STAGE-C-home.md` | Home, Daily/Weekly/User-choice/Weekly-top/Genre-mix, Radio, NotFound |
| `STAGE-D-library.md` | Search, Library, Liked, Playlists, Profile, Settings |
| `STAGE-E-tracks-chat.md` | TrackCard, TrackList, TrackCardSheet, Comments, Chat, Legal |
| `STAGE-F-artist.md` | ArtistView, AuthorView, ArtistStatsView |
| `STAGE-G-admin.md` | весь `frontend/src/admin/` |
| `STAGE-H-recap.md` | новый Wrapped/Recap (`/recap`) |
| `STAGE-I-upload.md` | UploadView, Upload tabs, Import |
| `STAGE-Z-finalize.md` | финальная сшивка, удаление мёртвого CSS, обновление docs |

## Порядок исполнения

1. **STAGE-0 — обязательно первым.** Один чат, последовательно. После завершения
   код запушен в `redesign/ios-2026`, `npm run build` зелёный.
2. **STAGE-A … I — параллельно.** Запускаются после Stage-0. Каждый — отдельный
   чат. Все они работают в `redesign/ios-2026`. Перед коммитом каждый делает
   `git pull --rebase`.
3. **STAGE-Z — последним.** Один чат. Прогоняет smoke-test, чистит legacy CSS,
   обновляет docs/design-system.md и TODO.md, готовит PR в main.

## Ветка и коммиты

- Все этапы → ветка `redesign/ios-2026` от свежего `main`.
- Conventional Commits, по одному коммиту на завершённый раздел этапа.
- Префикс scope = id этапа. Примеры:
  - `feat(redesign-0): scaffold motion primitives and tokens`
  - `feat(redesign-a): rebuild PlayerBar with liquid glass and beat pulse`
  - `feat(redesign-h): add Wrapped recap stories view`
  - `chore(redesign-z): remove legacy CSS and refresh docs`

## Критерии «готово» для всего редизайна

- `npm run build` (включая `tsc --noEmit`, bundle hygiene, admin bundle check) — green.
- `npm run test` — green.
- Главные сценарии (Auth → Home → играет трек → swipe-up Now Playing → лайк/queue/share) проходят без визуальных регрессий.
- `prefers-reduced-motion: reduce` отключает все loop-анимации.
- Bundle size публичного чанка не вырос больше чем на ~70 KB gzip
  (framer-motion ~30 KB gzip + наш код ~30–40 KB).
- `docs/design-system.md` отражает новые primitives и токены.
- `TODO.md` содержит запись о завершённом редизайне.
