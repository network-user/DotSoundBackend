import type { HomeMixShortcutIconId } from '@/components/home/HomeMixShortcutIcon'

export const MIX_SHORTCUT_TILES = [
  {
    path: '/daily-mix',
    labelKey: 'quickDaily' as const,
    profileIcon: 'calendar',
    shortcutIcon: 'mix-daily' as const,
  },
  {
    path: '/weekly-mix',
    labelKey: 'quickWeekly' as const,
    profileIcon: 'sparkle',
    shortcutIcon: 'mix-weekly' as const,
  },
  {
    path: '/weekly-top',
    labelKey: 'quickTop' as const,
    profileIcon: 'flame',
    shortcutIcon: 'mix-top' as const,
  },
  {
    path: '/user-choice',
    labelKey: 'quickUserChoice' as const,
    profileIcon: 'heart',
    shortcutIcon: 'mix-trending' as const,
  },
  {
    path: '/forgotten-treasures',
    labelKey: 'quickForgotten' as const,
    profileIcon: 'bookmark',
    shortcutIcon: 'mix-forgotten' as const,
  },
  {
    path: '/my-top',
    labelKey: 'quickMyTop' as const,
    profileIcon: 'star',
    shortcutIcon: 'mix-personal' as const,
  },
  {
    path: '/radio',
    labelKey: 'quickRadio' as const,
    profileIcon: 'radio',
    shortcutIcon: 'mix-daily' as HomeMixShortcutIconId,
  },
] as const

export const HOME_QUICK_VISIBLE_COUNT = 6

export type MixShortcutTile =
  (typeof MIX_SHORTCUT_TILES)[number]
