import { useCallback, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { useMainScrollRestore } from '@/hooks/useMainScrollRestore'
import { LikedView } from '@/views/LikedView'
import { PlaylistsView } from '@/views/PlaylistsView'
import { ImportedView } from '@/views/ImportedView'
import { FavoriteArtistsView } from '@/views/FavoriteArtistsView'
import { HistoryList } from '@/components/Profile/HistoryList'
import { Icon } from '@/components/Icon/Icon'
import { MotionPress } from '@/components/ui/MotionPress'
import { hapticSelection } from '@/lib/telegram'
import {
  usePlayerActions,
  usePlayerMeta,
} from '@/store/PlayerContext'

const SHORTCUTS = [
  {
    id: 'daily',
    icon: 'flame',
    labelKey: 'home.dayPlaylistTitle',
    route: '/daily-mix',
  },
  {
    id: 'weekly-top',
    icon: 'sparkle',
    labelKey: 'redesign.library.shortcutWeeklyTop',
    route: '/weekly-top',
  },
  {
    id: 'radio',
    icon: 'radio',
    labelKey: 'redesign.library.shortcutRadio',
    route: '/radio',
  },
  {
    id: 'my-top',
    icon: 'chart-bar',
    labelKey: 'redesign.library.shortcutMyTop',
    route: '/my-top',
  },
] as const

type Tab =
  | 'liked'
  | 'playlists'
  | 'artists'
  | 'imported'
  | 'history'

const STORAGE_KEY = 'library-tab'

const TABS: Array<{
  id: Tab
  labelKey: string
  icon: string
}> = [
  { id: 'liked', labelKey: 'library.tabLiked', icon: 'heart' },
  { id: 'playlists', labelKey: 'library.tabPlaylists', icon: 'list' },
  {
    id: 'artists',
    labelKey: 'library.tabArtists',
    icon: 'users-following',
  },
  {
    id: 'imported',
    labelKey: 'library.tabImported',
    icon: 'download',
  },
  { id: 'history', labelKey: 'library.tabHistory', icon: 'clock' },
]

function isTab(s: string | null): s is Tab {
  return (
    s === 'liked' ||
    s === 'playlists' ||
    s === 'artists' ||
    s === 'imported' ||
    s === 'history'
  )
}

function tabFromStorageDefault(): Tab {
  try {
    const v = localStorage.getItem(
      STORAGE_KEY,
    ) as string | null
    if (v && isTab(v)) return v
  } catch {
    /* ignore */
  }
  return 'liked'
}

export function LibraryView() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { openQueue } = usePlayerActions()
  const {
    queue,
    shuffleOn,
    track: currentTrack,
  } = usePlayerMeta()
  const [searchParams, setSearchParams] =
    useSearchParams()
  const didSync = useRef(false)
  const urlTab = searchParams.get('tab')

  useEffect(() => {
    if (didSync.current) return
    if (isTab(urlTab)) {
      didSync.current = true
      return
    }
    const storedTab =
      urlTab === null
        ? tabFromStorageDefault()
        : 'liked'
    setSearchParams({ tab: storedTab }, { replace: true })
    didSync.current = true
  }, [setSearchParams, urlTab])

  const tab: Tab = isTab(urlTab)
    ? urlTab
    : urlTab === null
      ? tabFromStorageDefault()
      : 'liked'

  useMainScrollRestore(`library:${tab}`)

  const handleTab = useCallback(
    (next: Tab) => {
      if (next !== tab) hapticSelection()
      setSearchParams({ tab: next }, { replace: true })
      try {
        localStorage.setItem(STORAGE_KEY, next)
      } catch {
        /* ignore */
      }
    },
    [setSearchParams, tab],
  )

  return (
    <section
      id="view-library"
      className="view active"
    >
      <div className="rd-lib-header">
        <div className="rd-lib-header__main">
          <h1 className="rd-lib-header__title">
            {t('nav.library')}
          </h1>
        </div>
        <MotionPress
          type="button"
          variant="subtle"
          haptic="selection"
          className="rd-lib-now"
          aria-label={t('redesign.player.openQueueAria')}
          onClick={openQueue}
        >
          <span className="rd-lib-now__icon" aria-hidden>
            <Icon
              name={shuffleOn ? 'shuffle' : 'queue'}
              size={18}
            />
          </span>
          <span className="rd-lib-now__body">
            <span className="rd-lib-now__mode">
              {t(
                shuffleOn
                  ? 'redesign.player.modeShuffle'
                  : 'redesign.player.modeSequential',
              )}
            </span>
            <span className="rd-lib-now__title">
              {currentTrack?.title ??
                t('redesign.player.queueEmpty')}
            </span>
          </span>
          <span className="rd-lib-now__count">
            <span>{t('redesign.player.queueUpNext')}</span>
            <strong>{queue.length}</strong>
          </span>
        </MotionPress>
      </div>

      <div className="rd-lib-shortcuts-wrap">
        <p className="rd-lib-shortcuts-eyebrow">
          {t('redesign.library.shortcutsEyebrow')}
        </p>
        <div className="rd-lib-shortcuts">
          {SHORTCUTS.map((s) => (
            <MotionPress
              key={s.id}
              variant="subtle"
              haptic="selection"
              className={`rd-lib-shortcut rd-lib-shortcut--${s.id}`}
              aria-label={t(s.labelKey)}
              onClick={() => navigate(s.route)}
            >
              <div className="rd-lib-shortcut__glow" aria-hidden />
              <div className="rd-lib-shortcut__icon" aria-hidden>
                <Icon name={s.icon} size={22} />
              </div>
              <span className="rd-lib-shortcut__label">
                {t(s.labelKey)}
              </span>
            </MotionPress>
          ))}
        </div>
      </div>

      <div
        className="library-tabs rd-lib-tabs"
        role="tablist"
        aria-label={t('nav.library')}
      >
        {TABS.map((row) => {
          const active = tab === row.id
          return (
            <MotionPress
              key={row.id}
              type="button"
              variant="ghost"
              haptic="selection"
              role="tab"
              aria-selected={active}
              data-active={active ? 'true' : 'false'}
              className="rd-lib-tab library-tab"
              onClick={() => handleTab(row.id)}
            >
              <Icon name={row.icon} size={16} />
              <span className="rd-lib-tab__label">
                {t(row.labelKey)}
              </span>
            </MotionPress>
          )
        })}
      </div>
      <div className="library-content">
        {tab === 'liked' && <LikedView embedded />}
        {tab === 'playlists' && (
          <PlaylistsView embedded />
        )}
        {tab === 'artists' && (
          <FavoriteArtistsView embedded />
        )}
        {tab === 'imported' && (
          <ImportedView embedded />
        )}
        {tab === 'history' && <HistoryList />}
      </div>
    </section>
  )
}
