# STAGE-G — Admin Panel

> Параллельный этап. Стартует после Stage-0.

## Цель

Админ-панель сейчас функциональная, но «инструментальная». Нужно поднять её
до уровня iOS desktop app — sidebar c blur, KPI-карточки с trend-арками,
гладкие переходы между route'ами, motion-аккордеоны для длинных списков.

Админ-чанк собирается отдельно (`build:bundle-only`), поэтому новые primitives
тут особенно безопасны (не раздуем публичный bundle).

## Owned files

```
frontend/src/admin/**
frontend/src/admin/styles/admin.css
```

> Это исключение из общего правила «не трогать стайлы вне redesign-*.css» —
> `admin.css` принадлежит чанку админки и редактируется этим этапом.

## No-touch

- Любые файлы вне `frontend/src/admin/`.
- В частности — `lib/api.ts`, `App.tsx`, `main.tsx`, общий `Icon.tsx`.
- Семантические state-tokens (`--state-ok/warn/error/unknown`) — остаются
  только в админке, как сейчас.

## Что сделать

### 1. AdminShell

- Sidebar — `glass--strong`, фиксированной ширины. Для узких экранов —
  drawer slide-in через `m.aside drag="x"`.
- Topbar — `glass--medium`, sticky, с заголовком текущей страницы и часами.
  При скролле — лёгкий depth-shadow.
- Main scroll-container — `m.div` с `VARIANTS_PAGE_SLIDE` для смены route.

### 2. Dashboard

- KPI-карточки — `<motion.article>` с `whileHover={{ y: -2 }}`. Внутри —
  крупное число (`tabular-nums`), label, sparkline. Trend-стрелки можно
  оставить, но монохромными в публичной части (state-tokens — только
  внутри admin).
- LineChart / AreaChart на `recharts` — стилизуем через `--text` /
  `--text-secondary` / `--surface-2` / `--accent`. Рамки — тонкие.
- Активные графики (online history) — гладкая «беговая» line-animation
  (по scroll, не loop).

### 3. DataTable

- Header rows — `glass--medium` sticky.
- Sortable headers — MotionPress с focus-ring.
- Pagination footer — capsule с MotionPress.

### 4. Routes (Tracks/Users/Artists/Complaints/Tasks/Logs/Metrics/Audit/Security/AudioCompute/etc.)

- Применить везде MotionPress + морф-иконки.
- Аккордеоны (например, lyrics-job detail) — `m.div` с
  `animate={{ height: 'auto' }}` для плавного раскрытия.

### 5. StepUpDialog / TotpInput

- Sheet — `m.div drag-y`. Поля TOTP — большие, моноширинные, focus-ring spring.
- Success — `<DynamicIsland kind="toast">` (импортируем из общего lib/island).

### 6. Realtime widgets

- LiveLogStream / WorkerDetailDrawer / LyricsJobDetail — гладкое появление
  новых rows через `AnimatePresence` + `m.li` initial scale 0.96.

### 7. Стили

`admin.css` — расширяем, не переписываем целиком (там много рабочего кода).
Префиксы новых классов: `.ad-shell-`, `.ad-topbar-`, `.ad-sidebar-`,
`.ad-table-`, `.ad-card-`, `.ad-step-`.

## Acceptance criteria

- [ ] AdminShell — sidebar с glass-strong, topbar с glass-medium.
- [ ] Dashboard — KPI с motion + sparkline.
- [ ] DataTable — sortable headers MotionPress, sticky glass header.
- [ ] StepUpDialog — sheet с drag-to-close + DynamicIsland confirmation.
- [ ] LiveLogStream — AnimatePresence на новых rows.
- [ ] reduced-motion корректен.
- [ ] `npm run build` зелёный (admin chunk + bundle hygiene check
      `scripts/check-admin-bundle.mjs` проходит).
- [ ] State-токены остались только в админке.

## Коммиты

```
feat(redesign-g): admin shell with glass sidebar and topbar
feat(redesign-g): dashboard KPI cards with motion and monochrome charts
feat(redesign-g): DataTable sticky glass header and motion sortable
feat(redesign-g): step-up dialog as bottom-sheet with island confirmations
feat(redesign-g): live log/worker streams with AnimatePresence
```
