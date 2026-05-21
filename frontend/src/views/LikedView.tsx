import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { TrackList } from '@/components/TrackList/TrackList'
import { MotionPress } from '@/components/ui/MotionPress'
import { useAutoLoadMore } from '@/hooks/useAutoLoadMore'
import { api } from '@/lib/api'
import { playFromPaginatedCollection } from '@/lib/paginatedPlayback'
import { getUserId } from '@/lib/telegram'
import { usePrefetchTracks } from '@/store/PrefetchContext'
import {
  usePlayerActions,
  usePlayerMeta,
} from '@/store/PlayerContext'
import type { LikedTrack, Track } from '@/types/api'

interface LikedViewProps {
  embedded?: boolean
}

type SourceFilter = 'all' | 'platform' | 'soundcloud' | 'other'

type LikedSort = 'newest' | 'oldest' | 'artist'

const PAGE_SIZE = 20
const PLAYBACK_QUEUE_SIZE = 80

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
  const { playTrack } = usePlayerActions()
  const { shuffleOn } = usePlayerMeta()
  const [tracks, setTracks] = useState<LikedTrack[] | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(false)
  const [sourceFilter, setSourceFilter] =
    useState<SourceFilter>('all')
  const [sortOrder, setSortOrder] =
    useState<LikedSort>('newest')
  const pageRef = useRef(1)

  const fetchPage = useCallback(
    async (
      page: number,
      filter: SourceFilter,
      sort: LikedSort,
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
        const data = await api.getLikedTracks(
          uid,
          page,
          PAGE_SIZE,
          filter !== 'all' ? filter : undefined,
          sort,
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
    fetchPage(1, sourceFilter, sortOrder, true)
  }, [sourceFilter, sortOrder, fetchPage])

  const displayedTracks = tracks

  const handlePlayTrack = useCallback(
    (track: Track) => {
      void playFromPaginatedCollection({
        track,
        loadedTracks: displayedTracks,
        playTrack,
        loadQueue: async (selected) => {
          const uid = getUserId()
          if (!uid) return []
          const data = await api.getLikedPlaybackQueue(
            uid,
            selected.id,
            PLAYBACK_QUEUE_SIZE,
            sourceFilter !== 'all' ? sourceFilter : undefined,
            sortOrder,
            shuffleOn,
            [selected.id],
          )
          return data.next_tracks
        },
      })
    },
    [
      displayedTracks,
      playTrack,
      shuffleOn,
      sortOrder,
      sourceFilter,
    ],
  )

  usePrefetchTracks(displayedTracks ?? null, 'library')

  const loadMore = useCallback(async () => {
    if (loading || !hasMore) return
    fetchPage(
      pageRef.current + 1,
      sourceFilter,
      sortOrder,
      false,
    )
  }, [loading, hasMore, sourceFilter, sortOrder, fetchPage])

  const sentinelRef = useAutoLoadMore({
    enabled: hasMore,
    loading,
    onLoadMore: loadMore,
  })

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

  const list = (
    <>
      <div className="rd-liked-top">
        {headerMeta}
        {sortBar}
        {filterBar}
      </div>
      <TrackList
        tracks={displayedTracks}
        flavor="liked"
        emptyMessage={t('redesign.library.likedEmpty')}
        onPlayTrack={handlePlayTrack}
        emptyCta={
          embedded
            ? {
                label: t('redesign.library.likedFindTracks'),
                onClick: () => navigate('/search'),
              }
            : undefined
        }
      />
      {hasMore && (
        <>
          <div ref={sentinelRef} aria-hidden />
          <MotionPress
            variant="ghost"
            haptic="light"
            className="rd-liked-more"
            onClick={loadMore}
            disabled={loading}
          >
            {loading
              ? t('redesign.library.likedLoading')
              : t('redesign.library.likedShowMore')}
          </MotionPress>
        </>
      )}
    </>
  )

  if (embedded) {
    return (
      <div className="library-embed liked-embed">{list}</div>
    )
  }

  return (
    <section id="view-liked" className="view active rd-liked">
      <div className="view-header rd-liked-header">
        <h2>{t('redesign.library.likedTitle')}</h2>
      </div>
      {list}
    </section>
  )
}
