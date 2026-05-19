import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { TrackList } from '@/components/TrackList/TrackList'
import { MotionPress } from '@/components/ui/MotionPress'
import { useAutoLoadMore } from '@/hooks/useAutoLoadMore'
import { api } from '@/lib/api'
import { usePrefetchTracks } from '@/store/PrefetchContext'
import type { Track } from '@/types/api'

interface ImportedViewProps {
  embedded?: boolean
}

type SourceFilter =
  | 'all'
  | 'telegram'
  | 'soundcloud'
  | 'yandex_music'
  | 'other'

const PAGE_SIZE = 50

const SOURCE_FILTERS: {
  key: SourceFilter
  labelKey: string
  apiValue?: string
}[] = [
  { key: 'all', labelKey: 'imported.sourceAll' },
  {
    key: 'telegram',
    labelKey: 'imported.sourceTelegram',
    apiValue: 'telegram',
  },
  {
    key: 'soundcloud',
    labelKey: 'imported.sourceSoundcloud',
    apiValue: 'soundcloud',
  },
  {
    key: 'yandex_music',
    labelKey: 'imported.sourceYandex',
    apiValue: 'yandex_music',
  },
  { key: 'other', labelKey: 'imported.sourceOther' },
]

const OTHER_SOURCES = new Set([
  'telegram',
  'soundcloud',
  'yandex_music',
])

function isOther(track: Track): boolean {
  const src = (
    track.imported_from ?? track.source_platform ?? ''
  ).toLowerCase()
  return src !== '' && !OTHER_SOURCES.has(src)
}

export function ImportedView({
  embedded = false,
}: ImportedViewProps) {
  const { t } = useTranslation()
  const [tracks, setTracks] = useState<Track[] | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(false)
  const [sourceFilter, setSourceFilter] =
    useState<SourceFilter>('all')
  const pageRef = useRef(1)

  const fetchPage = useCallback(
    async (
      page: number,
      filter: SourceFilter,
      reset: boolean,
    ) => {
      if (reset) setTracks(null)
      setLoading(true)
      try {
        const apiSource =
          filter !== 'all' && filter !== 'other'
            ? SOURCE_FILTERS.find((f) => f.key === filter)
                ?.apiValue
            : undefined
        const data = await api.getMyImportedTracks(
          page,
          PAGE_SIZE,
          apiSource,
        )
        let items = data.items
        if (filter === 'other') {
          items = items.filter(isOther)
        }
        setTracks((prev) =>
          reset || !prev ? items : [...prev, ...items],
        )
        setHasMore(
          filter === 'other'
            ? false
            : data.total > page * PAGE_SIZE,
        )
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

  const sentinelRef = useAutoLoadMore({
    enabled: hasMore,
    loading,
    onLoadMore: loadMore,
  })

  const headerMeta =
    Array.isArray(tracks) && tracks.length > 0 ? (
      <p className="rd-liked-meta">
        {t('imported.loaded', {
          count: tracks.length,
        })}
      </p>
    ) : null

  const filterBar = (
    <div
      className="rd-liked-source"
      role="tablist"
      aria-label={t('imported.sourceFilterAria')}
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
        {filterBar}
      </div>
      <TrackList
        tracks={tracks}
        emptyMessage={t('imported.empty')}
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
              ? t('imported.loading')
              : t('imported.showMore')}
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
    <section
      id="view-imported"
      className="view active rd-liked"
    >
      <div className="view-header rd-liked-header">
        <h2>{t('imported.title')}</h2>
      </div>
      {list}
    </section>
  )
}
