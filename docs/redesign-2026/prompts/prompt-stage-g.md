Ты — агент в чате, отвечаешь за поток G iOS-редизайна фронтенда DotSound. Это параллельный поток. Stage-0 уже завершён и запушен в ветку `redesign/ios-2026`.

## Твоя зона: Admin (вся админка)

Админка должна стать «iPad-style admin»: чистый, плотный, с большим заголовком, capsule-табами, плавными переходами между секциями. Никакого пёстрого UI — строгий монохром, как и публичный фронт.

## Твой контекст

Репозиторий: `c:\Users\User\PycharmProjects\DotSoundBackend`. Ветка: `redesign/ios-2026`. Фронт — React 18 + Vite + TypeScript + framer-motion (LazyMotion + domAnimation). Готовые primitives: `MotionPress`, `MorphIcon`, `SwipeRow`, `LongPressMenu`, `DynamicIsland`, `AmbientStage`, `KenBurnsCover`, `BeatPulse`, `HorizontalSnap`, `SharedCover`. Утилиты: `lib/motion.ts`, `lib/island.ts`, `lib/coverPalette.ts`.

Решения владельца: монохром, dark only, system-ui font-stack, framer-motion полный, big-bang. В админке используем те же primitives, что и публичный фронт, чтобы стиль был единым.

## Обязательно прочитать

1. `docs/redesign-2026/README.md`
2. `docs/redesign-2026/SHARED-CONTRACTS.md`
3. `docs/redesign-2026/STAGE-G-admin.md`
4. `docs/design-system.md`
5. `frontend/scripts/check-admin-bundle.mjs` (если есть) — лимиты на размер админ-чанка, не превышай.

## Жёсткие правила

1. Только `frontend/`. Бэкенд / privatecore / bot / compute не трогать.
2. Никаких новых npm-зависимостей.
3. Палитра — строгий монохром.
4. Тема — dark only.
5. Без эмодзи.
6. `prefers-reduced-motion: reduce` уважать.
7. PrivateCore-внутренности (имена стадий, моделей, провайдеров, веса) **не упоминать** в UI и коментариях. Бизнес-логика приходит с API — UI только отображает.
8. `lib/api.ts`, `types/api.ts`, `store/**` не трогать. Если API возвращает поле, которого нет в типах — запиши `TODO(redesign-2026):` и заглушку.
9. Conventional Commits, scope = `redesign-g`.

## Твои файлы

```
frontend/src/views/AdminPanel.tsx
frontend/src/views/AdminLogin.tsx
frontend/src/views/AdminApprovalView.tsx
frontend/src/views/AdminProfile.tsx
frontend/src/views/admin/** (все файлы)
frontend/src/components/Admin*.{ts,tsx}
frontend/src/styles/admin/** (все .css)
frontend/src/locales/i18n_extra2_ru.json (только namespace redesign.admin.*)
frontend/src/locales/i18n_extra2_en.json (только namespace redesign.admin.*)
```

## NO-TOUCH

```
frontend/src/lib/api.ts, types/api.ts, store/**, hooks/**
frontend/src/main.tsx, App.tsx
frontend/src/locales/ru.json, en.json, i18n_extra_*.json
frontend/src/components/Icon/Icon.tsx
frontend/src/components/PlayerBar/**, FullscreenLyrics/**, QueueSheet/** (Stage-A)
frontend/src/components/BottomNav/**, Auth/**, Onboarding/** (Stage-B)
frontend/src/components/TrackCard/**, TrackList/**, TrackCardSheet/** (Stage-E)
frontend/src/views/HomeView, ArtistView etc. (Stage-C/F)
frontend/src/views/SearchView, LibraryView etc. (Stage-D)
frontend/src/views/Now/Recap/Upload (Stage-A/H/I)
frontend/src/styles/tokens.css, global.css, components.css, animations.css, redesign-shared.css, redesign-player/nav/home/library/tracks/artist/recap/upload.css
frontend/src/components/ui/* (Stage-0)
frontend/src/lib/motion.ts, island.ts, coverPalette.ts
docs/redesign-2026/**
любой файл вне Owned-списка
```

## Что сделать

### AdminLogin

- Centered glass-strong card на фоне градиентов монохрома.
- Поля ввода с focus-spring.
- Кнопка login — `<MotionPress variant="primary">`.

### AdminPanel (shell)

- Заголовок страницы — large-title `--fs-lt` («Админка», подзаголовок — текущая роль/email).
- Capsule-tabs с `<m.span layoutId="admin-tab-indicator">` под активным.
- Каждая страница админки — секции карточек `glass--medium`.
- Page transitions через `<AnimatePresence mode="wait">` со slide-up для смены вкладок.

### Admin tables

- Rows карточками с `<MotionPress>` на клик-в-детали.
- В правой части ряда — actions через `<MotionPress variant="icon">` (а не голые кнопки).
- Статусы — pills `glass--medium` с outline-иконкой (без цветовых meanings — текст важнее: «pending», «approved», «rejected», «hidden»).
- Long-press → `<LongPressMenu>` с быстрыми actions для row.
- Toolbar (фильтры, сортировка) — sticky-top с blur-backdrop. Chips через `<MotionPress>`.

### Admin forms

- Input/select обёрнуть в Motion-wrappers с focus-spring (как в Auth).
- Submit — `<MotionPress variant="primary">`.
- Toggles → custom `<m.button>` capsule с `whileTap`.
- На submit success — `showIsland({ kind: 'toast', title: 'Сохранено' })`.

### Admin charts / dashboards

- Если есть статика — обернуть в `<m.div variants={VARIANTS_FADE_UP}>` со staggered detail-cards.
- Цифры — tabular-nums (var(--font-num-tabular-numbers)).

### AdminApprovalView (модерация треков)

- Sliding-card approval queue:
  - Карточка пендингового трека — большая обложка + метаданные.
  - Внизу — `<MotionPress variant="primary">` Approve, `<MotionPress variant="ghost">` Reject. На Reject — открывается reason input.
  - Между карточками переход через slide-up + spring (`<AnimatePresence mode="wait">`).
- Подтверждение action — DynamicIsland.

### AdminProfile

- Centered glass-strong card.
- Аватар, имя, роль.
- Logout button — `<MotionPress variant="ghost">`.

### CSS

Все стили — в существующих файлах `frontend/src/styles/admin/*.css`. Можешь создать `frontend/src/styles/admin/redesign-admin.css` (под него попадают новые классы; стиль сохраняй с префиксом `.adm-r-`). Не создавай дубль `redesign-admin` файла на корневом уровне `styles/`.

### i18n

Только `i18n_extra2_*.json` под `redesign.admin.*`.

### Bundle hygiene

- После завершения работы запусти `npm run build` и проверь, что admin-чанк не превысил лимит из `check-admin-bundle.mjs` (если такой скрипт уже стоит pre-build hook). Если превысил — ужми imports, lazy-load тяжёлые секции.

## Acceptance criteria

- [ ] AdminPanel: capsule-tabs с layoutId-индикатором.
- [ ] Page transitions через AnimatePresence работают между вкладками.
- [ ] Admin tables: rows с MotionPress, swipe или icon-actions, status-pill монохромные.
- [ ] AdminApprovalView: sliding-card approval с DynamicIsland подтверждениями.
- [ ] AdminLogin / AdminProfile: glass-strong + MotionPress.
- [ ] Forms — focus-spring, toggle-anim, success-Island.
- [ ] reduced-motion корректен.
- [ ] Admin bundle не превышает лимит.
- [ ] `npx tsc --noEmit` зелёный.
- [ ] `npm run build` зелёный.

## Workflow

1. `git fetch && git checkout redesign/ios-2026 && git pull --rebase`.
2. По одному коммиту на крупный кусок (login, shell+tabs, tables, forms, approval).
3. Перед коммитом: `git pull --rebase` + `npx tsc --noEmit` + `npm run build` (для проверки бандла).
4. Conventional Commits, scope `redesign-g`. Примеры:
   - `feat(redesign-g): rebuild AdminLogin with motion primitives`
   - `feat(redesign-g): admin shell with capsule tabs and layoutId indicator`
   - `feat(redesign-g): admin tables with MotionPress rows and pill statuses`
   - `feat(redesign-g): admin forms with focus-spring and island confirms`
   - `feat(redesign-g): sliding approval queue for moderation`
5. Push после каждого коммита.

Когда всё готово — сообщи отдельным сообщением.
