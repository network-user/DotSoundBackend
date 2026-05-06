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
import type { LikedTrack, Track } from '@/types/api'

interface LikedViewProps {
  embedded?: boolean
}

type SourceFilter = 'all' | 'platform' | 'soundcloud' | 'other'

type LikedSort = 'newest' | 'oldest' | 'artist'

const PAGE_SIZE = 20

function formatLikedAt(iso: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(new Date(iso))
}

const SOURCE_FILTERS: { key: SourceFilter; labelKey: string }[] = [
  { key: 'all', labelKey: 'redesign.library.sourceAll' },
  { key: 'platform', labelKey: 'redesign.library.sourcePlatform' },
  { key: 'soundcloud', labelKey: 'redesign.library.sourceSoundcloud' },
  { key: 'other', labelKey: 'redesign.library.sourceOther' },
]

const SORT_OPTIONS: { key: LikedSort; labelKey: string }[] = [
  { key: 'newest', labelKey: 'redesign.library.sortNewest' },
  { key: 'oldest', labelKey: 'redesign.library.sortOldest' },
  { key: 'artist', labelKey: 'redesign.library.sortArtist' },
]

export function LikedView({ embedded = false }: LikedViewProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [tracks, setTracks] = useState<LikedTrack[] | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(false)
  const [sourceFilter, setSourceFilter] =
    useState<SourceFilter>('all')
  const [sortOrder, setSortOrder] =
    useState<LikedSort>('newest')
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
        const data = await api.getLikedTracks(
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
        const da = a.liked_at
          ? new Date(a.liked_at).getTime()
          : 0
        const db = b.liked_at
          ? new Date(b.liked_at).getTime()
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
        {t('redesign.library.likedLoaded', {
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
      className="liked-source-filter rd-liked-source"
      role="tablist"
      aria-label={t('liked.sourceFilter', 'Фильтр по источнику')}
    >
      {SOURCE_FILTERS.map(({ key, labelKey }) => (
        <MotionPress
          key={key}
          variant="subtle"
          haptic="selection"
          role="tab"
          aria-selected={sourceFilter === key}
          className={`rd-liked-chip liked-source-chip${sourceFilter === key ? ' active' : ''}`}
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
      const lt = track as LikedTrack
      return lt.liked_at ? (
        <span className="liked-at-date">
          {formatLikedAt(lt.liked_at)}
        </span>
      ) : null
    },
    [],
  )

  const list = (
    <>
      <div className="rd-liked-top">
        {headerMeta}
        {sortBar}
        {filterBar}
      </div>
      <TrackList
        tracks={displayedTracks}
        emptyMessage={t('liked.empty', 'Ты ещё ничего не лайкал')}
        emptyCta={
          embedded
            ? {
                label: t('liked.findTracks', 'Найти треки'),
                onClick: () => navigate('/search'),
              }
            : undefined
        }
        renderExtra={renderExtra}
      />
      {hasMore && (
        <button
          className="load-more-btn"
          onClick={loadMore}
          disabled={loading}
        >
          {loading
            ? t('common.loading', 'Загрузка...')
            : t('common.showMore', 'Показать ещё')}
        </button>
      )}
    </>
  )

  if (embedded) {
    return (
      <div className="library-embed liked-embed">{list}</div>
    )
  }

  return (
    <section id="view-liked" className="view active">
      <div className="view-header">
        <h2>{t('liked.title', 'Мне нравится')}</h2>
      </div>
      {list}
    </section>
  )
}
