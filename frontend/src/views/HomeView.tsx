import { useEffect, useState } from 'react'
import { TrackList } from '@/components/TrackList/TrackList'
import { NotificationBell } from '@/components/Notifications/NotificationBell'
import { api } from '@/lib/api'
import type { Track } from '@/types/api'

export function HomeView() {
  const [tracks, setTracks] = useState<Track[] | null>(null)

  useEffect(() => {
    setTracks(null)
    api.getTracks({ size: 50 })
      .then((data) => setTracks(data.items))
      .catch(() => setTracks([]))
  }, [])

  return (
    <section id="view-home" className="view active">
      <div className="view-header view-header-row">
        <div>
          <h2>.sound</h2>
          <span className="hint">Слушай. Делись. Открывай.</span>
        </div>
        <NotificationBell />
      </div>
      <TrackList tracks={tracks} emptyMessage="Треков пока нет. Загрузи первый!" />
    </section>
  )
}
