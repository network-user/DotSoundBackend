import { useEffect, useState } from 'react'
import { TrackList } from '@/components/TrackList/TrackList'
import { api } from '@/lib/api'
import { userId } from '@/lib/telegram'
import type { Track } from '@/types/api'

interface Props {
  active: boolean
}

export function LikedView({ active }: Props) {
  const [tracks, setTracks] = useState<Track[] | null>(null)

  useEffect(() => {
    if (!active) return
    if (!userId) {
      setTracks([])
      return
    }
    setTracks(null)
    api.getLikedTracks(userId)
      .then((data) => setTracks(data.items))
      .catch(() => setTracks([]))
  }, [active])

  return (
    <section id="view-liked" className={`view${active ? ' active' : ''}`}>
      <div className="view-header">
        <h2>Мне нравится</h2>
      </div>
      {!userId ? (
        <p className="empty-hint">Войди через Telegram, чтобы видеть лайки.</p>
      ) : (
        <TrackList tracks={tracks} emptyMessage="Ты ещё ничего не лайкал" />
      )}
    </section>
  )
}
