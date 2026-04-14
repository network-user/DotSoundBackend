import { useCallback, useEffect, useRef, useState } from 'react'
import { TrackList } from '@/components/TrackList/TrackList'
import { api } from '@/lib/api'
import { getUserId } from '@/lib/telegram'
import type { Track } from '@/types/api'

interface Props {
  active: boolean
}

const PAGE_SIZE = 20

export function LikedView({ active }: Props) {
  const [tracks, setTracks] = useState<
    Track[] | null
  >(null)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(false)
  const pageRef = useRef(1)

  useEffect(() => {
    if (!active) return
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
  }, [active])

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

  return (
    <section
      id="view-liked"
      className={`view${active ? ' active' : ''}`}
    >
      <div className="view-header">
        <h2>Мне нравится</h2>
      </div>
      <TrackList
        tracks={tracks}
        emptyMessage="Ты ещё ничего не лайкал"
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
    </section>
  )
}
