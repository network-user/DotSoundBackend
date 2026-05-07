# Changelog

All notable changes to DotSoundBackend are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Added — iOS 2026 redesign (Mini App frontend)

**Foundation (shared primitives)**
- `MotionPress` — spring-press button with `primary | ghost | icon | subtle` variants, Telegram haptics, `prefers-reduced-motion` guard.
- `MorphIcon` — outline ↔ filled icon morph via Framer Motion for heart, play, home, search, library, radio, profile, chats, star, bookmark, flame, users-following.
- `DynamicIslandHost` + `lib/island.ts` — single top-of-screen pill for toasts, progress, now-playing, error notifications. `showIsland / updateIsland / dismissIsland` replace the legacy `useToast` hook in all redesigned surfaces.
- `AmbientStage` — desaturated three-layer radial gradient backdrop from cover palette.
- `KenBurnsCover` — slow pan/zoom over a static cover image.
- `BeatPulse` — BPM-locked subtle pulse animation.
- `SharedCover` — `layoutId`-based shared-element cover transitions.
- `SwipeRow` — rubber-band swipe-actions row with threshold-armed haptic.
- `LongPressMenu` — iOS-style context menu.
- `HorizontalSnap` — accessible snap-carousel with parallax.
- `lib/motion.ts` — re-exports `m`, `LazyMotion`, `domAnimation`, `useReducedMotion` plus named presets: `SPRING_GENTLE/SNAPPY/BOUNCY/LAYOUT`, `TWEEN_FAST/SLOW`, `VARIANTS_FADE_UP/SCALE_IN/PAGE_SLIDE/SHEET_SLIDE_UP`.

**Stage A — Player**
- `FullscreenLyrics` with Apple Music-style header and `BeatPulse` waveform.
- Player overlays and control animations polished with `MotionPress`.

**Stage B — Navigation & Auth**
- Stories-style `OnboardingView` with directional slide transitions.
- Import progress wired to `DynamicIsland` (`ImportActivityBanner` converted to headless driver).

**Stage C — Home & Radio**
- Map-driven section rendering in `HomeView`; toast calls migrated to `showIsland`.
- Radio, mix and discovery views with motion primitives.

**Stage D — Library**
- Library, Search (liked, playlists), Profile with `MotionPress` controls and i18n.

**Stage E — Track surfaces**
- `TrackCardSheet` drag-down close; all action buttons → `MotionPress`; `toast.*` → `showIsland`; hardcoded RU strings → i18n keys.
- `ChatView` iMessage-style header and composer.
- `TrackCard` long-press queue + share actions migrated to `showIsland`.
- `TrackList` empty-state CTA → `MotionPress`; queue toast → `showIsland`.

**Stage F — Artist / Album / Playlist / External**
- Route-based artist, album, playlist, genre and external-source views.
- `ArtistView` follow error → `showIsland`.

**Stage G — Admin (full refactor)**
- `AdminRangeSwitch` — new segmented control with `LayoutGroup` pill indicator.
- `DataTable` — sticky glass header, sort buttons → `MotionPress` with chevron icons.
- `StatusPill` — added outline icon per `StatusKind` (circle / alert-triangle / x / info).
- `DashboardRoute` — time-range and period controls → `MotionPress` / `AdminRangeSwitch`; strings → i18n.
- `TasksRoute` — all action buttons → `MotionPress`; cancel/retry errors → `showIsland` toasts.
- `SchedulesRoute` — row actions → `MotionPress`; mutation callbacks → `showIsland` toasts.
- `TracksRoute`, `UsersRoute`, `ArtistsRoute`, `ContainersRoute` — remaining bare buttons → `MotionPress`; period switches → `AdminRangeSwitch`.
- New i18n namespaces: `redesign.admin.dashboard.*`, `redesign.admin.tasks.*`, `redesign.admin.schedules.*`.

**Stage H — Recap**
- Stories-style Recap view, achievements, and profile entry point.

**Stage I — Upload & Import (full refactor)**
- `UploadFileTab` split into `UploadStepAudio`, `UploadStepDetails`, `UploadStepCover`, `UploadStepPreview`, `UploadComboBox`.
- `UrlImportTab` — unified URL import flow for SoundCloud, YouTube, Bandcamp.
- `ImportActivityBanner` converted to headless `DynamicIsland` driver; DOM attribute `data-import-ribbon` removed.
- New i18n namespaces: `redesign.upload.file.*`, `redesign.upload.url.*`, `redesign.upload.import.*`.

**Phase 3 — Global polish**
- `PlayerBar` overflow-menu buttons → `MotionPress` + i18n.
- `QueueSheet` clear/close/row/remove → `MotionPress`.
- `NowPlayingView` tab bar → `MotionPress`.
- `SearchView` external-result like buttons → `MotionPress`.
- `LegalView` back/doc-link buttons → `MotionPress`.
- `FullscreenLyrics` karaoke toggle → `MotionPress`.
- Dead `.import-activity-banner*` CSS (~90 lines) removed from `global.css`.
- `html[data-import-ribbon]` layout rules removed from `global.css`.

### Changed

- `docs/design-system.md` — added `AdminRangeSwitch` primitive; migration playbook updated with `MotionPress` and `showIsland` rules.
- `TODO.md` — iOS 2026 redesign marked complete.

---

## Legend

- **Stage A** — Player (PlayerBar, NowPlaying, Queue, EQ, Lyrics)
- **Stage B** — Nav shell, Auth, Onboarding
- **Stage C** — Home, Mixes, Radio
- **Stage D** — Library, Search, Liked, Playlists, Profile, Settings
- **Stage E** — TrackCard, TrackList, Sheet, Comments, Chat, Legal
- **Stage F** — Artist, Author, ArtistStats, external views
- **Stage G** — Admin
- **Stage H** — Recap
- **Stage I** — Upload & Import
