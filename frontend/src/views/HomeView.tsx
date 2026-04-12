import { useEffect, useState } from 'react'
import { TrackList } from '@/components/TrackList/TrackList'
import { NotificationBell } from '@/components/Notifications/NotificationBell'
import { api } from '@/lib/api'
import type { Track } from '@/types/api'

interface Props {
  active: boolean
}

export function HomeView({ active }: Props) {
  const [tracks, setTracks] = useState<Track[] | null>(null)

  const load = () => {
    setTracks(null)
    api.getTracks({ size: 50 })
      .then((data) => setTracks(data.items))
      .catch(() => setTracks([]))
  }

  useEffect(() => {
    if (active) load()
  }, [active])

  return (
    <section id="view-home" className={`view${active ? ' active' : ''}`}>
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
