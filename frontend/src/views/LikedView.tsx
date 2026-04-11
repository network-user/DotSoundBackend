import { useEffect, useState } from 'react'
import { TrackList } from '@/components/TrackList/TrackList'
import { api } from '@/lib/api'
import { getUserId } from '@/lib/telegram'
import type { Track } from '@/types/api'

interface Props {
  active: boolean
}

export function LikedView({ active }: Props) {
  const [tracks, setTracks] = useState<
    Track[] | null
  >(null)

  useEffect(() => {
    if (!active) return
    const uid = getUserId()
    if (!uid) {
      setTracks([])
      return
    }
    setTracks(null)
    api
      .getLikedTracks(uid)
      .then((data) => setTracks(data.items))
      .catch(() => setTracks([]))
  }, [active])

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
    </section>
  )
}
