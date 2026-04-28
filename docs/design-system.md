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

The palette is strictly **monochrome** (black + white + neutral
greys) and is **NOT** overridden by Telegram theme parameters.
The colour tokens defined in `frontend/src/styles/global.css`
(`--bg`, `--surface`, `--text`, `--text-secondary`, `--accent`,
`--border`, glass tokens `--glass-bg / --glass-blur /
--glass-border`) are the single source of truth in every theme
(Telegram Light / Dark / Sea / Custom).

`installTelegramThemeBridge()` in `frontend/src/lib/telegram.ts`
is intentionally a no-op kept only for backwards compatibility
of imports. If at some point a thin opt-in adaptation to the
Telegram theme is needed (e.g. matching only the system bar
colour, not the UI palette), it should be exposed through an
explicit user setting — never enabled automatically.

Surfaces that need an iOS-style frosted look (PlayerBar, BottomNav,
overflow menu, bottom sheets, modal backdrops) reuse the glass
tokens from `tokens.css`: fixed strips use `--glass-backdrop-fixed`
(and `--glass-backdrop-fixed-player` on the player bar); sticky bars
and sheets combine `--glass-blur-*` with `--glass-saturate`. When
`prefers-reduced-motion` or `prefers-reduced-data` applies,
`installGlassPerformanceClass()` adds `ds-low-glass` on
`<html>` and heavy backdrop filters fall back to opaque surfaces.

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
`<Icon name="…" />` call. New glyphs (for example `calendar` for
date-scoped content) are added to the same `PATHS` map.

## Status semantics (admin only)

The strict monochrome rule has **one** documented exception: the
status indicators in the admin panel. A monochrome status pill is
indistinguishable at a glance, which is unsafe for an
operations-facing surface.

Three semantic tokens live in `global.css`:

| Token              | Color           | Used for                                |
| ------------------ | --------------- | --------------------------------------- |
| `--state-ok`       | `#34C759` (green)  | healthy / running / success            |
| `--state-warn`     | `#FFCC00` (amber)  | open complaints / pending devices      |
| `--state-error`    | `#FF453A` (red)    | failed / unhealthy / locked-out        |
| `--state-unknown`  | neutral grey       | unknown / not applicable               |

These tokens are **only** consumed by `<StatusPill>` and
`<KpiCard accent="warn"|"error">` inside `frontend/src/admin/`.
The rest of the UI keeps the strict monochrome palette. Do not
reach for these tokens from regular user-facing components.

## Admin components

The admin chunk under `frontend/src/admin/` ships its own narrow
set of building blocks on top of the design system:

- `StatusPill` — color-aware status badge (see above).
- `KpiCard` — large numeric KPI with label/hint, used on the
  dashboard.
- `DataTable` — server-side pagination/sort wrapper around
  `@tanstack/react-table`.
- `LineChart` — `recharts` area chart pre-styled with
  `currentColor` and the project surface tokens.
- `JsonViewer` — read-only `<pre>`-based JSON dump for audit
  payloads.
- `LiveLogStream` — virtualized list rendered from the Loki
  query endpoint.
- `TotpInput` / `StepUpDialog` — TOTP UX primitives.

These components live next to the admin routes, not under
`frontend/src/components/ui/`, because they depend on
`@tanstack/react-query` + `recharts` + `qrcode` which the public
Mini App must not pay for.

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
