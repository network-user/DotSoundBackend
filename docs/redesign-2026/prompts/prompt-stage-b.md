Ты — агент в чате, отвечаешь за поток B iOS-редизайна фронтенда DotSound. Это параллельный поток. Stage-0 уже завершён и запушен в ветку `redesign/ios-2026`.

## Твоя зона: Bottom Nav, Auth, Onboarding, Banned, Install, Offline

Нижняя навигация и «лицо при первом запуске». Должно ощущаться как премиум-iOS-приложение.

## Твой контекст

Репозиторий: `c:\Users\User\PycharmProjects\DotSoundBackend`. Ветка: `redesign/ios-2026`. Фронт — React 18 + Vite + TypeScript + framer-motion (LazyMotion + domAnimation). Готовые primitives в `frontend/src/components/ui/`: `MotionPress`, `MorphIcon`, `SwipeRow`, `LongPressMenu`, `DynamicIsland`, `AmbientStage`, `KenBurnsCover`, `BeatPulse`, `HorizontalSnap`, `SharedCover`. Утилиты в `frontend/src/lib/`: `motion.ts`, `island.ts`, `coverPalette.ts`.

Решения владельца: монохром, dark only, system-ui font-stack, framer-motion полный, big-bang, референс — iOS 18 + visionOS Liquid Glass + Apple Music.

## Обязательно прочитать перед началом

1. `docs/redesign-2026/README.md`
2. `docs/redesign-2026/SHARED-CONTRACTS.md`
3. `docs/redesign-2026/STAGE-B-nav-auth.md`
4. `docs/design-system.md` (раздел Redesign 2026 primitives)

## Жёсткие правила

1. Только `frontend/`. Бэкенд / privatecore / bot / compute не трогать.
2. Никаких новых npm-зависимостей.
3. Палитра — строгий монохром. Никаких systemBlue/Pink/etc.
4. Тема — dark only.
5. Без эмодзи.
6. `prefers-reduced-motion: reduce` уважать везде.
7. PrivateCore-внутренности (провайдеры, модели) не упоминать ни в коде, ни в комментариях.
8. `lib/api.ts`, `types/api.ts`, `store/**` не трогать. Если нужны новые поля — `TODO(redesign-2026)` + заглушка.
9. Conventional Commits, scope = `redesign-b`.

## Твои файлы (можешь править ТОЛЬКО их)

```
frontend/src/components/BottomNav/BottomNav.tsx
frontend/src/components/Onboarding/**
frontend/src/components/Auth/**
frontend/src/components/BannedScreen/**
frontend/src/components/PwaInstall/InstallPrompt.tsx
frontend/src/components/ui/OfflineBanner.tsx
frontend/src/styles/redesign-nav.css
frontend/src/locales/i18n_extra2_ru.json (только namespace redesign.nav.*)
frontend/src/locales/i18n_extra2_en.json (только namespace redesign.nav.*)
```

## NO-TOUCH

```
frontend/src/lib/api.ts, types/api.ts, store/**, hooks/**
frontend/src/main.tsx, App.tsx
frontend/src/locales/ru.json, en.json, i18n_extra_*.json
frontend/src/components/Icon/Icon.tsx
frontend/src/styles/tokens.css, global.css, components.css, animations.css, redesign-shared.css
frontend/src/components/ui/* (primitives — Stage-0 владеет)
frontend/src/lib/motion.ts, island.ts, coverPalette.ts
docs/redesign-2026/**
любой файл вне Owned-списка
```

## Что сделать

### BottomNav v3

- Liquid Glass подложка (`.glass--liquid` или `.glass--strong`).
- Иконки → `<MorphIcon>` с filled-вариантами для `home`, `search`, `library`, `chats`, `profile`. Активный таб — filled.
- Текстовая подпись таба меньше (caption), tabular-nums где счётчики.
- Индикатор активного таба → `<m.span layoutId="bn-indicator">` с `transition={SPRING_LAYOUT}`. Плавно «перепрыгивает» между табами.
- Haptic `selection` на смену таба (используй существующий `hapticSelection` из `lib/telegram`).

Hint:
```tsx
<MotionPress key={path} variant="icon" haptic="selection"
  className={`rb-nav__btn${active ? ' is-active' : ''}`}
  onClick={() => navigate(path)} ariaLabel={t(labelKey)}>
  {active && <m.span layoutId="bn-indicator" className="rb-nav__bubble" transition={SPRING_LAYOUT} />}
  <MorphIcon name={icon} filled={active} size={22} />
  <span className="rb-nav__label">{t(labelKey)}</span>
</MotionPress>
```

### AuthScreen / EmailAuth / TelegramAuth

- Большая centered обложка-логотип. На фоне — KenBurnsCover на абстрактном градиенте монохрома.
- Все основные кнопки — `<MotionPress variant="primary">`.
- Поля ввода: focus-ring через `m.div animate` (легкое расширение поля при focus).
- Loader — pill через `showIsland({ kind: 'progress' })` вместо встроенных спиннеров.

### Onboarding

- Полноэкранный stories-style: 3–5 шагов, swipe between через `AnimatePresence` с direction-aware variants.
- Каждый шаг — large-title (`--fs-lt`), пояснение, primary CTA `<MotionPress variant="primary">`.
- OnboardingGenreScreen: chips через `<MotionPress>` + spring scale на pick. Selected → filled-state.
- OnboardingImportStep: список платформ с `<MorphIcon>`, активные filled. Прогресс импорта — `<DynamicIsland kind="progress" progress={...}>`.

### BannedScreen

- Карточка `glass--strong` по центру.
- Большой outlined `lock`-icon. Текст крупно, кнопки `<MotionPress>`.
- Монохром, без warn-state-токенов (правило публичного UI).

### InstallPrompt

- `glass--medium` контейнер.
- Анимация появления через `VARIANTS_FADE_UP`.
- Кнопки → `<MotionPress>`.

### OfflineBanner

- Заменить кастомный фиксированный баннер на DynamicIsland.
- При `navigator.onLine === false`:
  ```ts
  const id = showIsland({ kind: 'error', title: 'Нет соединения', durationMs: Infinity })
  ```
- При возвращении online — `dismissIsland(id)`.
- Сам компонент `OfflineBanner` оставить как точку монтирования effect-а.

### CSS

Все стили — в `frontend/src/styles/redesign-nav.css`. Префикс классов: `.rb-nav-`, `.rb-auth-`, `.rb-ob-`, `.rb-ban-`, `.rb-install-`.

### i18n

Только `i18n_extra2_*.json` под `redesign.nav.*`.

## Acceptance criteria

- [ ] BottomNav: морф-иконки + spring layoutId-индикатор + glass.
- [ ] Onboarding: stories-style, swipe между шагами, корректная навигация назад.
- [ ] AuthScreen: focus-ring анимирован, все кнопки MotionPress.
- [ ] BannedScreen: монохром, без cleve-state-токенов.
- [ ] InstallPrompt: glass-medium + motion-вход.
- [ ] OfflineBanner: переведён на DynamicIsland.
- [ ] reduced-motion корректен (выключает spring, scale-эффекты, KenBurns).
- [ ] `npx tsc --noEmit` зелёный.
- [ ] `npm run build` зелёный.

## Workflow

1. `git fetch && git checkout redesign/ios-2026 && git pull --rebase`.
2. Раздел за разделом, отдельные коммиты.
3. Перед коммитом: `git pull --rebase` + `npx tsc --noEmit`.
4. Conventional Commits, scope `redesign-b`. Примеры:
   - `feat(redesign-b): rebuild BottomNav with morph icons and spring indicator`
   - `feat(redesign-b): refresh AuthScreen visuals with motion primitives`
   - `feat(redesign-b): stories-style Onboarding with directional transitions`
   - `feat(redesign-b): polish BannedScreen, InstallPrompt, OfflineBanner`
5. Push после каждого коммита.

Когда всё готово — сообщи отдельным сообщением.
