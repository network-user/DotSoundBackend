import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { TrackList } from '@/components/TrackList/TrackList'
import { MotionPress } from '@/components/ui/MotionPress'
import { api } from '@/lib/api'
import { getUserId } from '@/lib/telegram'
import { usePrefetchTracks } from '@/store/PrefetchContext'
import type { DislikedTrack, Track } from '@/types/api'

type SourceFilter = 'all' | 'platform' | 'soundcloud' | 'other'

type DislikedSort = 'newest' | 'oldest' | 'artist'

const PAGE_SIZE = 20

function formatDislikedAt(iso: string, lang: string): string {
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

const SOURCE_FILTERS: { key: SourceFilter; labelKey: string }[] = [
  { key: 'all', labelKey: 'redesign.library.sourceAll' },
  { key: 'platform', labelKey: 'redesign.library.sourcePlatform' },
  { key: 'soundcloud', labelKey: 'redesign.library.sourceSoundcloud' },
  { key: 'other', labelKey: 'redesign.library.sourceOther' },
]

const SORT_OPTIONS: { key: DislikedSort; labelKey: string }[] = [
  { key: 'newest', labelKey: 'redesign.library.sortNewest' },
  { key: 'oldest', labelKey: 'redesign.library.sortOldest' },
  { key: 'artist', labelKey: 'redesign.library.sortArtist' },
]

export function DislikedView() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const lang = i18n.language
  const [tracks, setTracks] = useState<DislikedTrack[] | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(false)
  const [sourceFilter, setSourceFilter] =
    useState<SourceFilter>('all')
  const [sortOrder, setSortOrder] =
    useState<DislikedSort>('newest')
  const pageRef = useRef(1)

  const fetchPage = useCallback(
    async (page: number, filter: SourceFilter, reset: boolean) => {
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

  const displayedTracks = useMemo(() => {
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
        const aa = (a.artist ?? '').localeCompare(
          b.artist ?? '',
          undefined,
          { sensitivity: 'base' },
        )
        if (aa !== 0) return aa
        return a.title.localeCompare(b.title, undefined, {
          sensitivity: 'base',
        })
      })
    }
    return copy
  }, [tracks, sortOrder])

  usePrefetchTracks(displayedTracks ?? null, 'library')

  const loadMore = useCallback(async () => {
    if (loading || !hasMore) return
    fetchPage(pageRef.current + 1, sourceFilter, false)
  }, [loading, hasMore, sourceFilter, fetchPage])

  const headerMeta =
    Array.isArray(tracks) && tracks.length > 0 ? (
      <p className="rd-liked-meta">
        {t('redesign.library.dislikedLoaded', {
          count: tracks.length,
        })}
      </p>
    ) : null

  const sortBar = (
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
          data-active={sortOrder === key ? 'true' : 'false'}
          onClick={() => {
            if (sortOrder !== key) setSortOrder(key)
          }}
        >
          {t(labelKey)}
        </MotionPress>
      ))}
    </div>
  )

  const filterBar = (
    <div
      className="rd-liked-source"
      role="tablist"
      aria-label={t('redesign.library.sourceFilterAria')}
    >
      {SOURCE_FILTERS.map(({ key, labelKey }) => (
        <MotionPress
          key={key}
          variant="subtle"
          haptic="selection"
          role="tab"
          aria-selected={sourceFilter === key}
          className="rd-liked-chip"
          data-active={sourceFilter === key ? 'true' : 'false'}
          onClick={() => {
            if (sourceFilter !== key) setSourceFilter(key)
          }}
        >
          {t(labelKey)}
        </MotionPress>
      ))}
    </div>
  )

  const renderExtra = useCallback(
    (track: Track) => {
      const dt = track as DislikedTrack
      return dt.disliked_at ? (
        <span className="rd-liked-date">
          {formatDislikedAt(dt.disliked_at, lang)}
        </span>
      ) : null
    },
    [lang],
  )

  return (
    <div className="library-embed liked-embed rd-disliked-profile">
      <div className="rd-liked-top">
        {headerMeta}
        {sortBar}
        {filterBar}
      </div>
      <TrackList
        tracks={displayedTracks}
        emptyMessage={t('redesign.library.dislikedEmpty')}
        emptyCta={{
          label: t('redesign.library.dislikedFindTracks'),
          onClick: () => navigate('/search'),
        }}
        renderExtra={renderExtra}
      />
      {hasMore && (
        <MotionPress
          variant="ghost"
          haptic="light"
          className="rd-liked-more"
          onClick={loadMore}
          disabled={loading}
        >
          {loading
            ? t('redesign.library.dislikedLoading')
            : t('redesign.library.dislikedShowMore')}
        </MotionPress>
      )}
    </div>
  )
}
