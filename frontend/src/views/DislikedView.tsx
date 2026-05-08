import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { MotionPress } from '@/components/ui/MotionPress'
import { TrackCard } from '@/components/TrackCard/TrackCard'
import { SwipeRow } from '@/components/ui/SwipeRow'
import { Icon } from '@/components/Icon/Icon'
import { api } from '@/lib/api'
import { getUserId } from '@/lib/telegram'
import { showIsland } from '@/lib/island'
import { usePrefetchTracks } from '@/store/PrefetchContext'
import { useLikes } from '@/store/LikesContext'
import { usePlayerActions } from '@/store/PlayerContext'
import type { DislikedTrack } from '@/types/api'

type SourceFilter = 'all' | 'platform' | 'soundcloud' | 'other'

type DislikedSort = 'newest' | 'oldest' | 'artist'

type DateGroup = 'today' | 'week' | 'month' | 'earlier'

const PAGE_SIZE = 20

const SOURCE_FILTERS: {
  key: SourceFilter
  labelKey: string
}[] = [
  { key: 'all', labelKey: 'redesign.library.sourceAll' },
  {
    key: 'platform',
    labelKey: 'redesign.library.sourcePlatform',
  },
  {
    key: 'soundcloud',
    labelKey: 'redesign.library.sourceSoundcloud',
  },
  {
    key: 'other',
    labelKey: 'redesign.library.sourceOther',
  },
]

const SORT_OPTIONS: {
  key: DislikedSort
  labelKey: string
}[] = [
  {
    key: 'newest',
    labelKey: 'redesign.library.sortNewest',
  },
  {
    key: 'oldest',
    labelKey: 'redesign.library.sortOldest',
  },
  {
    key: 'artist',
    labelKey: 'redesign.library.sortArtist',
  },
]

const DATE_GROUP_ORDER: DateGroup[] = [
  'today',
  'week',
  'month',
  'earlier',
]

const DATE_GROUP_KEYS: Record<DateGroup, string> = {
  today: 'redesign.library.dislikedGroupToday',
  week: 'redesign.library.dislikedGroupWeek',
  month: 'redesign.library.dislikedGroupMonth',
  earlier: 'redesign.library.dislikedGroupEarlier',
}

function getDateGroup(iso: string): DateGroup {
  const date = new Date(iso)
  const now = new Date()
  if (date.toDateString() === now.toDateString()) {
    return 'today'
  }
  const diffMs = now.getTime() - date.getTime()
  const diffDays = diffMs / (1000 * 60 * 60 * 24)
  if (diffDays < 7) return 'week'
  if (diffDays < 30) return 'month'
  return 'earlier'
}

function formatDislikedAt(
  iso: string,
  lang: string,
): string {
  const safeLang = lang || 'en'
  try {
    return new Intl.DateTimeFormat(safeLang, {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    }).format(new Date(iso))
  } catch {
    return new Intl.DateTimeFormat('en', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    }).format(new Date(iso))
  }
}

export function DislikedView() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const lang = i18n.language
  const { isLiked, toggleLike } = useLikes()
  const { addToQueue } = usePlayerActions()

  const [tracks, setTracks] = useState<
    DislikedTrack[] | null
  >(null)
  const [apiTotal, setApiTotal] = useState<number | null>(
    null,
  )
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(false)
  const [sourceFilter, setSourceFilter] =
    useState<SourceFilter>('all')
  const [sortOrder, setSortOrder] =
    useState<DislikedSort>('newest')
  const [searchQuery, setSearchQuery] = useState('')
  const [removingIds, setRemovingIds] = useState<
    Set<number>
  >(new Set())

  const pageRef = useRef(1)
  const sentinelRef = useRef<HTMLDivElement | null>(null)
  const searchRef = useRef<HTMLInputElement | null>(null)

  const fetchPage = useCallback(
    async (
      page: number,
      filter: SourceFilter,
      reset: boolean,
    ) => {
      const uid = getUserId()
      if (!uid) {
        setTracks([])
        return
      }
      if (reset) setTracks(null)
      setLoading(true)
      try {
        const data = await api.getDislikedTracks(
          uid,
          page,
          PAGE_SIZE,
          filter !== 'all' ? filter : undefined,
        )
        setTracks((prev) =>
          reset || !prev
            ? data.items
            : [...prev, ...data.items],
        )
        setApiTotal(data.total)
        setHasMore(data.has_more)
        pageRef.current = page
      } catch {
        if (reset) setTracks([])
      } finally {
        setLoading(false)
      }
    },
    [],
  )

  useEffect(() => {
    pageRef.current = 1
    fetchPage(1, sourceFilter, true)
  }, [sourceFilter, fetchPage])

  const loadMore = useCallback(() => {
    if (loading || !hasMore) return
    fetchPage(
      pageRef.current + 1,
      sourceFilter,
      false,
    )
  }, [loading, hasMore, sourceFilter, fetchPage])

  useEffect(() => {
    const el = sentinelRef.current
    if (!el) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (
          entries[0].isIntersecting &&
          hasMore &&
          !loading
        ) {
          loadMore()
        }
      },
      { threshold: 0.1 },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [hasMore, loading, loadMore])

  const sortedTracks = useMemo(() => {
    if (!tracks || tracks.length === 0) return tracks
    const copy = [...tracks]
    if (sortOrder === 'oldest') {
      copy.sort((a, b) => {
        const da = a.disliked_at
          ? new Date(a.disliked_at).getTime()
          : 0
        const db = b.disliked_at
          ? new Date(b.disliked_at).getTime()
          : 0
        return da - db
      })
    } else if (sortOrder === 'artist') {
      copy.sort((a, b) => {
        const cmp = (a.artist ?? '').localeCompare(
          b.artist ?? '',
          undefined,
          { sensitivity: 'base' },
        )
        if (cmp !== 0) return cmp
        return a.title.localeCompare(b.title, undefined, {
          sensitivity: 'base',
        })
      })
    }
    return copy
  }, [tracks, sortOrder])

  const filteredTracks = useMemo(() => {
    if (!sortedTracks) return sortedTracks
    const q = searchQuery.trim().toLowerCase()
    if (!q) return sortedTracks
    return sortedTracks.filter(
      (tr) =>
        tr.title.toLowerCase().includes(q) ||
        (tr.artist ?? '').toLowerCase().includes(q),
    )
  }, [sortedTracks, searchQuery])

  usePrefetchTracks(filteredTracks ?? null, 'library')

  const groupedTracks = useMemo(() => {
    if (!filteredTracks || filteredTracks.length === 0) {
      return null
    }
    if (sortOrder === 'artist') return null
    const map = new Map<DateGroup, DislikedTrack[]>()
    for (const tr of filteredTracks) {
      const g = tr.disliked_at
        ? getDateGroup(tr.disliked_at)
        : 'earlier'
      const arr = map.get(g) ?? []
      arr.push(tr)
      map.set(g, arr)
    }
    return DATE_GROUP_ORDER.filter((g) =>
      map.has(g),
    ).map((g) => ({ key: g, tracks: map.get(g)! }))
  }, [filteredTracks, sortOrder])

  const handleRemoveDislike = useCallback(
    async (track: DislikedTrack) => {
      const uid = getUserId()
      if (!uid || removingIds.has(track.id)) return
      setRemovingIds((prev) => new Set([...prev, track.id]))
      try {
        await api.toggleDislike(uid, track.id)
        setTracks((prev) =>
          prev
            ? prev.filter((tr) => tr.id !== track.id)
            : prev,
        )
        setApiTotal((prev) =>
          prev !== null ? Math.max(0, prev - 1) : prev,
        )
        showIsland({
          kind: 'toast',
          title: t(
            'redesign.library.dislikedRemovedToast',
          ),
          durationMs: 2500,
        })
      } catch {
        showIsland({
          kind: 'error',
          title: t(
            'redesign.library.dislikedRemoveFail',
          ),
          iconName: 'alert-triangle',
          durationMs: 3000,
        })
      } finally {
        setRemovingIds((prev) => {
          const next = new Set(prev)
          next.delete(track.id)
          return next
        })
      }
    },
    [removingIds, t],
  )

  const renderTrackRow = useCallback(
    (track: DislikedTrack) => {
      const liked = isLiked(track.id)
      return (
        <div
          key={track.id}
          className="track-list-item re-tl-item rd-disliked-item"
        >
          <SwipeRow
            leftAction={{
              icon: liked ? 'heart' : 'heart-outline',
              label: t('redesign.tracks.swipeLike'),
              onTrigger: () => {
                void toggleLike(track.id)
              },
            }}
            rightAction={{
              icon: 'queue',
              label: t('redesign.tracks.addQueue'),
              onTrigger: () => {
                addToQueue(track)
                showIsland({
                  kind: 'toast',
                  title: t(
                    'redesign.tracks.longPressQueued',
                  ),
                  durationMs: 2000,
                })
              },
            }}
          >
            <TrackCard track={track} />
          </SwipeRow>
          <div className="rd-disliked-extra">
            {track.disliked_at && (
              <span className="rd-liked-date">
                {formatDislikedAt(track.disliked_at, lang)}
              </span>
            )}
            <button
              className="rd-disliked-remove-btn"
              onClick={() =>
                void handleRemoveDislike(track)
              }
              disabled={removingIds.has(track.id)}
              aria-label={t(
                'redesign.library.dislikedRemoveAria',
              )}
            >
              <Icon name="x" size={11} />
              {t('redesign.library.dislikedRemove')}
            </button>
          </div>
        </div>
      )
    },
    [
      isLiked,
      toggleLike,
      addToQueue,
      t,
      lang,
      handleRemoveDislike,
      removingIds,
    ],
  )

  const isSearching =
    searchQuery.trim().length > 0

  const metaLine = (() => {
    if (!Array.isArray(filteredTracks)) return null
    if (isSearching) {
      return (
        <p className="rd-liked-meta">
          {t('redesign.library.dislikedSearchCount', {
            count: filteredTracks.length,
          })}
        </p>
      )
    }
    if (apiTotal !== null && apiTotal > 0) {
      return (
        <p className="rd-liked-meta">
          {t('redesign.library.dislikedShowing', {
            count: tracks?.length ?? 0,
            total: apiTotal,
          })}
        </p>
      )
    }
    return null
  })()

  const chips = (
    <div className="rd-disliked-controls">
      <div
        className="rd-liked-sort"
        role="tablist"
        aria-label={t('redesign.library.sortAria')}
      >
        {SORT_OPTIONS.map(({ key, labelKey }) => (
          <MotionPress
            key={key}
            variant="subtle"
            haptic="selection"
            role="tab"
            aria-selected={sortOrder === key}
            className="rd-liked-chip liked-source-chip"
            data-active={
              sortOrder === key ? 'true' : 'false'
            }
            onClick={() => {
              if (sortOrder !== key) setSortOrder(key)
            }}
          >
            {t(labelKey)}
          </MotionPress>
        ))}
      </div>
      <div
        className="rd-liked-source"
        role="tablist"
        aria-label={t(
          'redesign.library.sourceFilterAria',
        )}
      >
        {SOURCE_FILTERS.map(({ key, labelKey }) => (
          <MotionPress
            key={key}
            variant="subtle"
            haptic="selection"
            role="tab"
            aria-selected={sourceFilter === key}
            className="rd-liked-chip"
            data-active={
              sourceFilter === key ? 'true' : 'false'
            }
            onClick={() => {
              if (sourceFilter !== key) {
                setSourceFilter(key)
              }
            }}
          >
            {t(labelKey)}
          </MotionPress>
        ))}
      </div>
    </div>
  )

  const emptyState = (() => {
    if (tracks === null) {
      return (
        <div className="track-list re-tl-root">
          <div className="loader" />
        </div>
      )
    }
    if (isSearching && filteredTracks?.length === 0) {
      return (
        <div className="rd-disliked-search-empty">
          <p>
            {t(
              'redesign.library.dislikedSearchEmpty',
            )}
          </p>
        </div>
      )
    }
    if (tracks.length === 0) {
      return (
        <div className="track-list re-tl-root">
          <div className="empty-state-block">
            <p className="empty-hint">
              {t('redesign.library.dislikedEmpty')}
            </p>
            <MotionPress
              variant="ghost"
              haptic="selection"
              className="empty-cta"
              onClick={() => navigate('/search')}
            >
              {t(
                'redesign.library.dislikedFindTracks',
              )}
            </MotionPress>
          </div>
        </div>
      )
    }
    return null
  })()

  const content = (() => {
    if (emptyState) return emptyState
    if (!filteredTracks || filteredTracks.length === 0) {
      return null
    }

    if (groupedTracks) {
      return (
        <div className="track-list re-tl-root">
          {groupedTracks.map(({ key, tracks: grpTracks }) => (
            <div
              key={key}
              className="rd-disliked-group"
            >
              <h3 className="rd-disliked-group-header">
                {t(DATE_GROUP_KEYS[key])}
              </h3>
              {grpTracks.map(renderTrackRow)}
            </div>
          ))}
        </div>
      )
    }

    return (
      <div className="track-list re-tl-root">
        {filteredTracks.map(renderTrackRow)}
      </div>
    )
  })()

  return (
    <div className="library-embed liked-embed rd-disliked-profile">
      <div className="rd-liked-top">
        <div className="rd-disliked-search-wrap">
          <label
            className="rd-disliked-search"
            aria-label={t(
              'redesign.library.dislikedSearch',
            )}
          >
            <Icon
              name="search"
              size={15}
              className="rd-disliked-search-icon"
            />
            <input
              ref={searchRef}
              type="search"
              value={searchQuery}
              onChange={(e) =>
                setSearchQuery(e.target.value)
              }
              placeholder={t(
                'redesign.library.dislikedSearch',
              )}
              autoComplete="off"
              autoCorrect="off"
              spellCheck={false}
            />
            {searchQuery && (
              <button
                className="rd-disliked-search-clear"
                onClick={() => {
                  setSearchQuery('')
                  searchRef.current?.focus()
                }}
                aria-label="Clear search"
                type="button"
              >
                <Icon name="x" size={14} />
              </button>
            )}
          </label>
        </div>
        <p className="rd-disliked-hint">
          <Icon name="thumbs-down" size={12} />
          {t('redesign.library.dislikedHint')}
        </p>
        {metaLine}
        {chips}
      </div>
      {content}
      <div
        ref={sentinelRef}
        className="rd-disliked-sentinel"
        aria-hidden="true"
      />
      {loading && tracks !== null && (
        <div className="rd-disliked-load-indicator">
          <div className="loader loader--sm" />
        </div>
      )}
    </div>
  )
}
