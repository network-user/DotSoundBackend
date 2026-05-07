# STAGE-B — Bottom Nav, Auth, Onboarding, Banned, Install, Offline

> Параллельный этап. Стартует после Stage-0.
> `git pull --rebase` перед коммитом.

## Цель

Привести нижнюю навигацию к Apple Music / iOS-стилю (морф-иконки, spring
indicator, Liquid Glass). Освежить онбординг, экраны авторизации и системные
оверлеи (banned, install prompt, offline banner) — это «лицо при первом
запуске» и оно должно ощущаться как премиум-iOS-приложение.

## Owned files

```
frontend/src/components/BottomNav/BottomNav.tsx
frontend/src/components/Onboarding/**
frontend/src/components/Auth/**
frontend/src/components/BannedScreen/**
frontend/src/components/PwaInstall/InstallPrompt.tsx
frontend/src/components/ui/OfflineBanner.tsx
frontend/src/styles/redesign-nav.css
```

## No-touch

См. SHARED-CONTRACTS § 6 + § 5. Особенно: `App.tsx`, `main.tsx`, `Icon.tsx`,
`tokens.css`, `lib/api.ts`, `types/api.ts`.

## Что сделать

### 1. BottomNav v3

- Liquid Glass подложка (`.glass--liquid` или `.glass--strong`).
- Иконки — `<MorphIcon>` с filled-вариaнтами (`home`, `search`, `library`,
  `chats`, `profile`). При активации морфит outline → filled.
- Текстовая подпись таба — может остаться, но шрифт меняем на SF-стек (он уже
  системный); меньшие caption + tabular-nums где счётчики.
- Индикатор активного таба — `<m.span layoutId="bn-indicator">` который плавно
  «перепрыгивает» под активным табом spring-ом. Ширина = ширине иконки.
- Haptic — `selection` на смену таба (уже есть).

### 2. Auth screens

- `AuthScreen` — большая centered обложка-логотип (KenBurnsCover на
  абстрактной градиент-подложке монохромной), `<MotionPress variant="primary">` для
  основной кнопки.
- `EmailAuth`, `TelegramAuth` — карточки с `glass--medium`, поля с focus-ring
  spring (поле слегка увеличивается на focus).
- Loader — pill `<DynamicIsland>` с `kind: 'progress'`.

### 3. Onboarding

- Полноэкранный сторис-стиль: 3–5 шагов, swipe between через
  `framer-motion` `AnimatePresence` + `direction-aware variants`.
- Каждый шаг — большой заголовок (large-title `--fs-lt`), пояснение, primary
  CTA `<MotionPress variant="primary">`.
- Onboarding genre screen — chips с `<MotionPress>` + spring scale; выбранные
  получают filled-state.
- Onboarding import — список платформ через `MorphIcon`, активный — filled.
  Прогресс в виде `<DynamicIsland>` с progress kind.

### 4. BannedScreen

- Карточка `glass--strong` по центру. Большой outlined `lock`-icon
  (через MotionPress hover micro). Текст крупный, кнопки `MotionPress`.
- Без цветных warn-токенов — монохром (правило).

### 5. InstallPrompt + OfflineBanner

- Заменить кастомный backdrop на `glass--medium` через `<m.div>` с
  `VARIANTS_FADE_UP`.
- Кнопки — `<MotionPress>`.
- OfflineBanner — pill с `<DynamicIsland>` (а не отдельный фиксированный
  баннер). Использовать `showIsland({ kind: 'error', durationMs: Infinity })` пока
  оффлайн, и `dismissIsland(id)` когда `online`.

## Hint-снипет

```tsx
// BottomNav.tsx
import { m } from '@/lib/motion'
import { MorphIcon } from '@/components/ui/MorphIcon'
import { MotionPress } from '@/components/ui/MotionPress'

export function BottomNav() {
  ...
  return (
    <nav id="nav" className="rb-nav glass--liquid" aria-label="...">
      {NAV_ITEMS.map(({ path, icon, labelKey }) => {
        const active = isActive(path)
        return (
          <MotionPress key={path}
            variant="icon"
            className={`rb-nav__btn${active ? ' is-active' : ''}`}
            haptic="selection"
            onClick={() => navigate(path)}
            ariaLabel={t(labelKey)}
          >
            {active && <m.span layoutId="bn-indicator" className="rb-nav__bubble" transition={SPRING_LAYOUT} />}
            <MorphIcon name={icon} filled={active} size={22} />
            <span className="rb-nav__label">{t(labelKey)}</span>
          </MotionPress>
        )
      })}
    </nav>
  )
}
```

## Acceptance criteria

- [ ] BottomNav: морф-иконки + spring indicator + glass.
- [ ] Onboarding: stories-style с swipe между шагами, без багов навигации
      назад.
- [ ] AuthScreen: focus-ring анимирован, все кнопки `MotionPress`.
- [ ] BannedScreen: монохром, без сleve-ровых акцентов.
- [ ] InstallPrompt: `glass--medium`, motion-вход.
- [ ] OfflineBanner: переведён на DynamicIsland.
- [ ] reduced-motion корректен.
- [ ] `npm run build` зелёный.

## Коммиты

```
feat(redesign-b): rebuild BottomNav with morph icons and spring indicator
feat(redesign-b): refresh AuthScreen visuals with motion primitives
feat(redesign-b): stories-style Onboarding with directional transitions
feat(redesign-b): polish BannedScreen, InstallPrompt, OfflineBanner
```
