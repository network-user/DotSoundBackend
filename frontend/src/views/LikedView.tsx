import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { TrackList } from '@/components/TrackList/TrackList'
import { api } from '@/lib/api'
import { getUserId } from '@/lib/telegram'
import type { Track } from '@/types/api'

interface LikedViewProps {
  /** Внутри LibraryView — без дублирующего заголовка */
  embedded?: boolean
}

const PAGE_SIZE = 20

export function LikedView({ embedded = false }: LikedViewProps) {
  const navigate = useNavigate()
  const [tracks, setTracks] = useState<
    Track[] | null
  >(null)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(false)
  const pageRef = useRef(1)

  useEffect(() => {
    const uid = getUserId()
    if (!uid) {
      setTracks([])
      return
    }
    setTracks(null)
    pageRef.current = 1
    api
      .getLikedTracks(uid, 1, PAGE_SIZE)
      .then((data) => {
        setTracks(data.items)
        setHasMore(data.has_more)
        pageRef.current = 1
      })
      .catch(() => setTracks([]))
  }, [])

  const loadMore = useCallback(async () => {
    if (loading || !hasMore) return
    const uid = getUserId()
    if (!uid) return
    setLoading(true)
    try {
      const nextPage = pageRef.current + 1
      const data = await api.getLikedTracks(
        uid, nextPage, PAGE_SIZE,
      )
      setTracks((prev) =>
        prev ? [...prev, ...data.items] : data.items,
      )
      setHasMore(data.has_more)
      pageRef.current = nextPage
    } catch {
      /* keep current state */
    } finally {
      setLoading(false)
    }
  }, [loading, hasMore])

  const list = (
    <>
      <TrackList
        tracks={tracks}
        emptyMessage="Ты ещё ничего не лайкал"
        emptyCta={
          embedded
            ? {
                label: 'Найти треки',
                onClick: () => navigate('/search'),
              }
            : undefined
        }
      />
      {hasMore && (
        <button
          className="load-more-btn"
          onClick={loadMore}
          disabled={loading}
        >
          {loading ? 'Загрузка...' : 'Показать ещё'}
        </button>
      )}
    </>
  )

  if (embedded) {
    return <div className="library-embed liked-embed">{list}</div>
  }

  return (
    <section
      id="view-liked"
      className="view active"
    >
      <div className="view-header">
        <h2>Мне нравится</h2>
      </div>
      {list}
    </section>
  )
}
