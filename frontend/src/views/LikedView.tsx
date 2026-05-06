import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { TrackList } from '@/components/TrackList/TrackList'
import { api } from '@/lib/api'
import { getUserId } from '@/lib/telegram'
import { usePrefetchTracks } from '@/store/PrefetchContext'
import type { LikedTrack, Track } from '@/types/api'

interface LikedViewProps {
  embedded?: boolean
}

type SourceFilter = 'all' | 'platform' | 'soundcloud' | 'other'

const PAGE_SIZE = 20

function formatLikedAt(iso: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(new Date(iso))
}

const SOURCE_FILTERS: { key: SourceFilter; label: string }[] = [
  { key: 'all', label: 'Все' },
  { key: 'platform', label: 'Платформа' },
  { key: 'soundcloud', label: 'SoundCloud' },
  { key: 'other', label: 'Другие' },
]

export function LikedView({ embedded = false }: LikedViewProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [tracks, setTracks] = useState<LikedTrack[] | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(false)
  const [sourceFilter, setSourceFilter] =
    useState<SourceFilter>('all')
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

  usePrefetchTracks(tracks ?? null, 'library')

  const loadMore = useCallback(async () => {
    if (loading || !hasMore) return
    fetchPage(pageRef.current + 1, sourceFilter, false)
  }, [loading, hasMore, sourceFilter, fetchPage])

  const filterBar = (
    <div
      className="liked-source-filter"
      role="tablist"
      aria-label={t('liked.sourceFilter', 'Фильтр по источнику')}
    >
      {SOURCE_FILTERS.map(({ key, label }) => (
        <button
          key={key}
          role="tab"
          aria-selected={sourceFilter === key}
          className={`liked-source-chip${sourceFilter === key ? ' active' : ''}`}
          onClick={() => {
            if (sourceFilter !== key) setSourceFilter(key)
          }}
        >
          {label}
        </button>
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
      {filterBar}
      <TrackList
        tracks={tracks}
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
