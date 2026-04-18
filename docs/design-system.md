# DotSound Design System

This document describes the design tokens and the shared UI
primitives that ship with the Mini App. They live in
`frontend/src/styles/tokens.css`,
`frontend/src/styles/components.css` and
`frontend/src/components/ui/`.

The system targets Telegram WebApp first and the desktop browser
second. It deliberately stays monochrome; the only colour token
that ever changes is the optional accent.

## Foundations

### 8pt grid

Spacing is exposed via `--space-1 .. --space-10`, mapping to
`4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 56 / 72` pixels. Use the
tokens directly instead of literal pixel values.

### Type scale

`--fs-12`, `--fs-13`, `--fs-14`, `--fs-15`, `--fs-16`, `--fs-18`,
`--fs-22`, `--fs-28`, `--fs-36`, `--fs-48`. Line-heights:
`--lh-tight (1.2)`, `--lh-normal (1.5)`, `--lh-loose (1.7)`.

### Radius

`--r-sm (6px)`, `--r-md (10px)`, `--r-lg (16px)`, `--r-xl (24px)`,
`--r-pill (999px)`.

### Motion

| Token            | Value                                 |
| ---------------- | ------------------------------------- |
| `--dur-fast`     | 120ms                                 |
| `--dur-med`      | 220ms                                 |
| `--dur-slow`     | 360ms                                 |
| `--ease-standard`| `cubic-bezier(.2, 0, 0, 1)`           |
| `--ease-emph`    | `cubic-bezier(.3, 0, 0, 1.2)`         |

All `--dur-*` tokens collapse to `0ms` automatically when the
user has `prefers-reduced-motion: reduce`.

### Tap targets and safe areas

- Minimum tap-target: `--tap = 44px` (Apple HIG / WCAG 2.1).
- Safe area helpers: `--safe-top`, `--safe-right`, `--safe-bottom`,
  `--safe-left`. The fixed bottom UI (`#nav`, `#player-bar`,
  `#main`) already accounts for `env(safe-area-inset-bottom)`.

### Z-index scale

```
--z-nav:    80
--z-player: 90
--z-sheet:  110
--z-modal:  130
--z-toast:  200
```

## Colour and theming

The base palette stays monochrome (`--bg`, `--surface`, `--text`,
`--text-secondary`, `--accent`). When the WebApp exposes Telegram
theme parameters, they are remapped onto a subset of the base
tokens by `installTelegramThemeBridge()` in
`frontend/src/lib/telegram.ts`. The bridge only activates when
the document gains the `tg-theme-on` class — pure-browser users
keep the default dark monochrome look.

## UI primitives

### `Press`

Accessible button with built-in tap target, focus ring and
press-state animation.

```tsx
<Press variant="primary" iconOnly={false}>Save</Press>
<Press variant="icon" aria-label="Закрыть">
  <Icon name="x" size={18} />
</Press>
```

### `Sheet`

Bottom sheet with swipe-down dismiss, Escape support and a visible
drag handle. Uses CSS transitions only (no Framer Motion).

```tsx
<Sheet open={open} onClose={close} ariaLabel="Now playing">
  …
</Sheet>
```

### `EmptyState`

Standard empty/error layout with a stroke icon, title, hint and
optional CTA.

```tsx
<EmptyState
  icon="empty-staff"
  title="Лайков пока нет"
  hint="Поставь сердечко на любимом треке"
/>
```

### `SkeletonList`

Six-row shimmer placeholder for list views during initial load.

### `OfflineBanner`

Renders a pill banner at the top of the screen whenever
`navigator.onLine` is false. Mounted once in `App.tsx`.

## Iconography

All icons are defined in `frontend/src/components/Icon/Icon.tsx`,
stroke-only, sharing the 24×24 view-box. Whenever a component is
about to use a Unicode glyph or an emoji, replace it with an
`<Icon name="…" />` call.

## Telegram-native helpers

`frontend/src/lib/telegram.ts` exposes:

- `installTelegramThemeBridge()` — once per session.
- `installViewportListener()` — keeps `--vh` in sync with the
  Telegram viewport.
- `setBackButton(visible, onClick)` — wires the native back button
  to a navigation callback. Returns a cleanup function.
- `haptic('light' | 'medium' | 'heavy')` — impact feedback for
  buttons.
- `hapticNotification('success' | 'warning' | 'error')` —
  notification haptics for completed actions.

## Migration playbook

1. Replace literal spacing with `--space-*`.
2. Replace literal duration values with `--dur-*` and easing.
3. Replace bespoke colour values with the monochrome tokens.
4. Use `Press`/`Sheet`/`EmptyState`/`SkeletonList` instead of
   re-implementing them in component files.
5. Run `npx tsc --noEmit` and the visual smoke test before
   committing.
