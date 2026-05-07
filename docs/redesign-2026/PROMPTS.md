# Готовые промпты для параллельных чатов

Каждый блок ниже — самодостаточный промпт для нового чата. Скопируй целиком,
вставь в новый Cursor-чат с правильной рабочей директорией.

Все промпты исходят из того, что:

- Репозиторий: `c:\Users\User\PycharmProjects\DotSoundBackend`.
- Уже создана документация в `docs/redesign-2026/`.
- Stage-0 будет (или уже был) запущен **первым** и запушен в
  `redesign/ios-2026`. Остальные стартуют только после Stage-0.

> Замечание: после первой реплики ассистента в каждом чате убедись, что он
> прочитал `SHARED-CONTRACTS.md` и свой собственный `STAGE-X-*.md`. Если он
> начал что-то делать без этого — останови и попроси сначала прочитать.

---

## STAGE-0 — Foundation (первым, последовательно)

```
Запускаю iOS-редизайн фронтенда DotSound. Сейчас фаза-фундамент. Это первый
этап, его нужно сделать до того как пойдут параллельные потоки.

Прочитай в строгом порядке:
1. docs/redesign-2026/README.md
2. docs/redesign-2026/SHARED-CONTRACTS.md
3. docs/redesign-2026/STAGE-0-foundation.md

Затем выполни всё, что указано в STAGE-0-foundation.md шаг за шагом:
создание ветки redesign/ios-2026, установка framer-motion, расширение
tokens.css, primitives в frontend/src/components/ui/, lib/motion.ts,
lib/island.ts, lib/coverPalette.ts, scaffold-CSS пустышки на каждый этап,
DynamicIslandHost в App.tsx, stub-вью для /now-playing и /recap,
обновление Icon.tsx со всеми нужными новыми иконками, каркас locales
i18n_extra2_*.json под redesign.* namespace, и раздел в design-system.md.

Жёсткие правила:
- Только frontend. Не трогать app/, alembic/, dotsound_private_core/, bot/,
  ComputeWorker.
- Без новых npm-зависимостей кроме framer-motion@^11.11.17.
- Монохром. Без iOS-палитры. Dark only.
- Без эмодзи в UI.
- prefers-reduced-motion соблюсти везде.
- Никаких упоминаний внутренних провайдеров/моделей PrivateCore (HARD RULE).

Когда всё готово:
- npm run build должен быть зелёным;
- DynamicIslandHost рендерится, /now-playing и /recap stub открываются;
- запушь один коммит в redesign/ios-2026 с conventional message:
  feat(redesign-0): scaffold iOS redesign foundation (motion, primitives,
  tokens, routes)

Сообщи мне отдельным сообщением, что Stage-0 готов и можно стартовать
параллельные чаты.
```

---

## STAGE-A — Player Stack

```
Стартую параллельный поток iOS-редизайна. Stage-0 уже запушен в
redesign/ios-2026 — тебе доступны primitives и токены.

Прочитай в строгом порядке:
1. docs/redesign-2026/README.md
2. docs/redesign-2026/SHARED-CONTRACTS.md
3. docs/redesign-2026/STAGE-A-player.md

Затем:
- git checkout redesign/ios-2026 && git pull --rebase
- работай ТОЛЬКО в файлах из секции Owned files в STAGE-A-player.md;
- НЕ трогай файлы из секции No-touch и из SHARED-CONTRACTS § 6;
- используй уже готовые primitives из frontend/src/components/ui/ и
  утилиты из frontend/src/lib/ (motion, island, coverPalette);
- никаких новых npm-зависимостей;
- стили — только в frontend/src/styles/redesign-player.css с префиксом
  .rp-...;
- i18n — только в frontend/src/locales/i18n_extra2_*.json под namespace
  redesign.player.*;
- монохром, dark-only, без эмодзи, prefers-reduced-motion соблюсти;
- никаких упоминаний внутренних провайдеров/моделей PrivateCore.

Что сделать (см. STAGE-A для деталей и acceptance):
- PlayerBar v3 (Liquid Glass, MorphIcon play/pause/heart, BeatPulse,
  SharedCover, MotionPress, ambient glow от обложки);
- Now Playing полноэкранный экран на /now-playing (shared cover,
  AmbientStage + KenBurns, табы Now/Lyrics/Queue, drag-down close);
- FullscreenLyrics — Apple Music лейаут с маленькой обложкой и beat-pulse;
- QueueSheet — swipe-actions на каждом ряду, beat-pulse на текущем;
- Equalizer — bottom-sheet через m.div drag-down, MotionPress на toggle.

Перед каждым коммитом: git pull --rebase + npx tsc --noEmit + npm run build.
Пуш в redesign/ios-2026. Conventional Commits, scope = redesign-a.
По ходу работы обновляй docs/design-system.md ТОЛЬКО если реально меняешь
контракт primitive (что на этом этапе не должно происходить — primitives
уже зафиксированы Stage-0).

Когда все acceptance criteria из STAGE-A выполнены — сообщи отдельным
сообщением.
```

---

## STAGE-B — Bottom Nav, Auth, Onboarding, Banned, Install, Offline

```
Параллельный поток iOS-редизайна. Stage-0 уже залит.

Прочитай:
1. docs/redesign-2026/README.md
2. docs/redesign-2026/SHARED-CONTRACTS.md
3. docs/redesign-2026/STAGE-B-nav-auth.md

git checkout redesign/ios-2026 && git pull --rebase

Работай ТОЛЬКО в файлах из Owned files раздела STAGE-B. Любой файл
из SHARED-CONTRACTS § 6 / § 5 (особенно App.tsx, main.tsx, Icon.tsx,
tokens.css, lib/api.ts) — НЕ ТРОГАТЬ.

Стили — только в frontend/src/styles/redesign-nav.css, префикс .rb-...
i18n — i18n_extra2_*.json под redesign.nav.*.
Монохром, dark-only, prefers-reduced-motion, без эмодзи, без новых deps,
без упоминания внутренних провайдеров/моделей PrivateCore.

Что сделать (детали и acceptance в STAGE-B):
- BottomNav v3 — MorphIcon, layoutId-индикатор, Liquid Glass;
- AuthScreen / EmailAuth / TelegramAuth — MotionPress, focus-ring spring;
- Onboarding — stories-style swipe between, MorphIcon на genre chips,
  DynamicIsland на import progress;
- BannedScreen — монохром, MotionPress;
- InstallPrompt — glass-medium + motion;
- OfflineBanner — переключить на DynamicIsland.

Пeред коммитом: git pull --rebase + tsc + build. Conventional Commits,
scope = redesign-b. Когда всё готово — сообщи.
```

---

## STAGE-C — Home, Discovery, Radio, NotFound

```
Параллельный поток iOS-редизайна. Stage-0 уже залит.

Прочитай:
1. docs/redesign-2026/README.md
2. docs/redesign-2026/SHARED-CONTRACTS.md
3. docs/redesign-2026/STAGE-C-home.md

git checkout redesign/ios-2026 && git pull --rebase

Работай ТОЛЬКО в файлах Owned files STAGE-C. SHARED-CONTRACTS § 6 / § 5
не трогать (особенно lib/api.ts, App.tsx, main.tsx, tokens.css, Icon.tsx,
TrackCard и TrackList — они принадлежат другим этапам).

Стили — только redesign-home.css, префикс .rh-...
i18n — i18n_extra2_*.json под redesign.home.*.
Монохром, dark-only, prefers-reduced-motion, без эмодзи, без новых deps,
без упоминания внутренних провайдеров/моделей PrivateCore.

Что сделать (детали и acceptance в STAGE-C):
- HomeView v3 — hero с AmbientStage+KenBurns, Quick-grid с MorphIcon,
  HorizontalSnap карусели с parallax, followed-artists strip, genre mixes;
- DailyMixView/WeeklyMixView/UserChoiceView/WeeklyTopView/GenreMixView —
  hero + Play all + Shuffle, оборачивать существующий TrackList без
  правки его внутренностей;
- RadioView — атмосферная сцена, BeatPulse, мудовые карточки;
- NotFoundView — лаконично с MotionPress.

Если каких-то полей в API не хватает — TODO(redesign-2026) и заглушка,
api.ts/types/api.ts НЕ править.

Перед коммитом: git pull --rebase + tsc + build. Conventional Commits,
scope = redesign-c. Когда всё готово — сообщи.
```

---

## STAGE-D — Library, Search, Liked, Playlists, Profile, Settings

```
Параллельный поток iOS-редизайна. Stage-0 уже залит.

Прочитай:
1. docs/redesign-2026/README.md
2. docs/redesign-2026/SHARED-CONTRACTS.md
3. docs/redesign-2026/STAGE-D-library.md

git checkout redesign/ios-2026 && git pull --rebase

Работай ТОЛЬКО в файлах Owned files STAGE-D. TrackCard и TrackList —
не править их внутренности (они у Stage-E). Можно оборачивать в SwipeRow
и motion.div, но без изменения файлов TrackCard.tsx / TrackList.tsx.

Стили — redesign-library.css, префиксы .rd-...
i18n — i18n_extra2_*.json под redesign.library.*.
Монохром, dark-only, prefers-reduced-motion, без эмодзи, без новых deps,
без упоминания внутренних провайдеров/моделей PrivateCore.

Что сделать (детали и acceptance в STAGE-D):
- SearchView — capsule input с focus-spring, chips-фильтры с MorphIcon,
  staggered секции;
- LibraryView — capsule tabs с layoutId-индикатором;
- LikedView — sticky-header с metadata, swipe-actions на rows;
- PlaylistsView — grid 2-col + LongPressMenu;
- ProfileView — hero c KenBurns на градиентной подложке, секции
  glass-medium;
- Settings — toggles с motion, DynamicIsland подтверждения.

Перед коммитом: git pull --rebase + tsc + build. Conventional Commits,
scope = redesign-d. Когда всё готово — сообщи.
```

---

## STAGE-E — TrackCard, TrackList, TrackCardSheet, Comments, Chat, Legal

```
Параллельный поток iOS-редизайна. Stage-0 уже залит.

Прочитай:
1. docs/redesign-2026/README.md
2. docs/redesign-2026/SHARED-CONTRACTS.md
3. docs/redesign-2026/STAGE-E-tracks-chat.md

git checkout redesign/ios-2026 && git pull --rebase

Работай ТОЛЬКО в файлах Owned files STAGE-E. PlayerBar / FullscreenLyrics /
QueueSheet / NowPlayingView — не трогать (они у Stage-A). Координация:
TrackCardSheet и Now Playing используют одинаковый layoutId
"cover-{trackId}" через <SharedCover>; убедись что обложка обёрнута
в <SharedCover trackId={...}> для shared-element transition.

Стили — redesign-tracks.css, префиксы .rt-...
i18n — i18n_extra2_*.json под redesign.tracks.*.
Монохром, dark-only, prefers-reduced-motion, без эмодзи, без новых deps,
без упоминания внутренних провайдеров/моделей PrivateCore.

Что сделать (детали и acceptance в STAGE-E):
- TrackCard — MotionPress, MorphIcon, LongPressMenu, SharedCover;
- TrackList — staggered mount, swipeable rows;
- TrackCardSheet — обёртки и переходы через AnimatePresence + SharedCover;
- Comments — long-press context-menu, motion layout reply branches;
- Chat (ChatBubble, VoicePlayer/Recorder, ChatView) — MotionPress
  везде, beat-pulse на voice player;
- ChatsView — swipe-actions на rows, glass header;
- LegalView/LegalDocView — list-стиль iOS Settings, читабельность;
- ComplaintModal — AnimatePresence шаги.

Перед коммитом: git pull --rebase + tsc + build. Conventional Commits,
scope = redesign-e. Когда всё готово — сообщи.
```

---

## STAGE-F — Artist & Author

```
Параллельный поток iOS-редизайна. Stage-0 уже залит.

Прочитай:
1. docs/redesign-2026/README.md
2. docs/redesign-2026/SHARED-CONTRACTS.md
3. docs/redesign-2026/STAGE-F-artist.md

git checkout redesign/ios-2026 && git pull --rebase

Работай ТОЛЬКО в файлах Owned files STAGE-F.

Стили — redesign-artist.css, префиксы .ra-...
i18n — i18n_extra2_*.json под redesign.artist.*.
Монохром, dark-only, prefers-reduced-motion, без эмодзи, без новых deps,
без упоминания внутренних провайдеров/моделей PrivateCore.

Что сделать (детали и acceptance в STAGE-F):
- ArtistView — hero с AmbientStage + KenBurns + параллакс на scroll,
  source-switcher chips с MorphIcon, follow-кнопка с burst spring,
  discography как HorizontalSnap, similar artists slider;
- AuthorView — компактная версия паттернов ArtistView;
- ArtistStatsView — KPI карточка + recharts в монохром-стиле.

Перед коммитом: git pull --rebase + tsc + build. Conventional Commits,
scope = redesign-f. Когда всё готово — сообщи.
```

---

## STAGE-G — Admin Panel

```
Параллельный поток iOS-редизайна. Stage-0 уже залит.

Прочитай:
1. docs/redesign-2026/README.md
2. docs/redesign-2026/SHARED-CONTRACTS.md
3. docs/redesign-2026/STAGE-G-admin.md

git checkout redesign/ios-2026 && git pull --rebase

Работай ТОЛЬКО в frontend/src/admin/** (в т.ч. admin/styles/admin.css).
Это эксклюзивная зона данного этапа.

Не трогать:
- frontend/src/admin вне моей фазы — никакой;
- frontend/src/components/ui/* (primitives Stage-0);
- любые файлы вне frontend/src/admin/** — НИКАКИЕ;
- App.tsx, main.tsx, Icon.tsx, tokens.css.

Стили — расширять frontend/src/admin/styles/admin.css, не переписывать
целиком. Префиксы новых классов: .ad-...
Монохром в публичном UI остаётся, в админке state-токены
(--state-ok/warn/error/unknown) — допустимы как сейчас (см. design-system).
prefers-reduced-motion соблюсти.

Что сделать (детали и acceptance в STAGE-G):
- AdminShell — sidebar glass-strong, topbar glass-medium, drag-drawer на
  узких экранах;
- Dashboard — KPI motion-карточки + sparklines, recharts стиль монохром;
- DataTable — sticky glass header, MotionPress sortable;
- StepUpDialog/TotpInput — bottom-sheet drag-y + DynamicIsland confirm
  (использовать общий lib/island);
- LiveLogStream/WorkerDetailDrawer/LyricsJobDetail — AnimatePresence
  на новых rows.

Использовать готовые primitives (MotionPress, MorphIcon, SwipeRow и др.)
там, где это уместно для desktop UX.

Перед коммитом: git pull --rebase + tsc + build (включая
scripts/check-admin-bundle.mjs). Conventional Commits, scope = redesign-g.
Когда всё готово — сообщи.
```

---

## STAGE-H — Wrapped / Recap

```
Параллельный поток iOS-редизайна. Stage-0 уже залит.

Прочитай:
1. docs/redesign-2026/README.md
2. docs/redesign-2026/SHARED-CONTRACTS.md
3. docs/redesign-2026/STAGE-H-recap.md

git checkout redesign/ios-2026 && git pull --rebase

Работай ТОЛЬКО в:
- frontend/src/views/RecapView.tsx (заменить stub из Stage-0);
- frontend/src/components/Recap/** (новая папка);
- frontend/src/styles/redesign-recap.css.

App.tsx уже зарегистрировал /recap (Stage-0). Не трогать.

Стили — redesign-recap.css, префиксы .rr-...
i18n — i18n_extra2_*.json под redesign.recap.*.
Монохром, dark-only, prefers-reduced-motion, без эмодзи, без новых deps,
без упоминания внутренних провайдеров/моделей PrivateCore.

Что сделать (детали и acceptance в STAGE-H):
- RecapView с поддержкой ?period=week|year, sсегментированный
  progress-bar, autoplay через сторис, gestures (tap left/right,
  long-press pause, swipe-down close);
- минимум 5 типов сторис: top-track, top-artist, total-minutes,
  genre-snapshot, pinned-moment (заглушки если данных нет);
- AmbientStage + KenBurns на каждой сторис.

API НЕ ПРАВИТЬ. Использовать существующие методы api.ts. Если данных нет —
TODO(redesign-2026) и заглушка.

Перед коммитом: git pull --rebase + tsc + build. Conventional Commits,
scope = redesign-h. Когда всё готово — сообщи.
```

---

## STAGE-I — Upload & Import

```
Параллельный поток iOS-редизайна. Stage-0 уже залит.

Прочитай:
1. docs/redesign-2026/README.md
2. docs/redesign-2026/SHARED-CONTRACTS.md
3. docs/redesign-2026/STAGE-I-upload.md

git checkout redesign/ios-2026 && git pull --rebase

Работай ТОЛЬКО в файлах Owned files STAGE-I (UploadView, Upload/**,
Import/**, redesign-upload.css).

Стили — redesign-upload.css, префиксы .ru-...
i18n — i18n_extra2_*.json под redesign.upload.*.
Монохром, dark-only, prefers-reduced-motion, без эмодзи, без новых deps,
без упоминания внутренних провайдеров/моделей PrivateCore.

Что сделать (детали и acceptance в STAGE-I):
- UploadView — capsule tabs с layoutId-индикатором, AnimatePresence на
  переходах табов;
- UploadFileTab drop-zone — spring scale на dragOver, мощный preview
  карточкой;
- Bandcamp/YouTube/SoundCloud tabs — те же паттерны, prog через
  DynamicIsland;
- ImportSourcePicker — list MotionPress + MorphIcon;
- ImportActivityBanner — переключить на DynamicIsland progress.

Перед коммитом: git pull --rebase + tsc + build. Conventional Commits,
scope = redesign-i. Когда всё готово — сообщи.
```

---

## STAGE-Z — Finalize (последовательно, ПОСЛЕ всех A–I)

```
Финальная сборка iOS-редизайна. Все этапы A–I запушены в
redesign/ios-2026 и владелец считает наполнение готовым.

Прочитай:
1. docs/redesign-2026/README.md
2. docs/redesign-2026/SHARED-CONTRACTS.md
3. docs/redesign-2026/STAGE-Z-finalize.md

git checkout redesign/ios-2026 && git pull --rebase

Выполни всё из STAGE-Z-finalize.md:
- сквозной smoke по сценариям (Auth → Home → Now Playing → Liked →
  Search → Artist → Profile → Recap);
- reduced-motion аудит;
- удаление мёртвого CSS из global.css/components.css/animations.css
  (только после rg-подтверждения, что класс не используется);
- удаление дубликатов primitives (Press/Sheet) если все мигрировали;
- bundle-size аудит, верификация LazyMotion + domAnimation;
- финал i18n (договориться со мной, сливать ли redesign.* namespace
  в основные ru.json/en.json или оставлять в i18n_extra2);
- обновить docs/design-system.md и TODO.md (раздел "iOS Redesign 2026
  released", дата);
- npm run test, npm run e2e (если возможно);
- запушить и создать PR из redesign/ios-2026 в main с заголовком
  "feat(frontend): iOS UI redesign 2026" и ссылкой на
  docs/redesign-2026/README.md в body.

Conventional Commits, scope = redesign-z. Когда PR создан — сообщи URL.
```

---

## Подсказки по запуску

1. **Запускай Stage-0 первым.** Без него у параллельных чатов нет
   primitives и они начнут изобретать своё, конфликтуя.
2. **Используй один и тот же workspace path** для всех чатов:
   `c:\Users\User\PycharmProjects\DotSoundBackend`. Все чаты работают в
   одном репо, в одной ветке `redesign/ios-2026`.
3. **Нумеруй чаты** в Cursor по id stage (Stage-A chat, Stage-B chat...),
   так проще ориентироваться.
4. **Если хочешь снизить параллелизм** — стартуй сначала A, B, C
   (наиболее видимые экраны), позже D, E, F, потом G/H/I.
5. **Конфликты git** при правильном следовании Owned files невозможны.
   Если они всё-таки происходят — почти всегда это знак, что один из
   потоков «вылез» за свою зону. Откатывай и поправь промпт того
   потока.
