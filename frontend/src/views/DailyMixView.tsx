import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { TrackList } from '@/components/TrackList/TrackList'
import { Icon } from '@/components/Icon/Icon'
import { api } from '@/lib/api'
import type { Track } from '@/types/api'

export function DailyMixView() {
  const navigate = useNavigate()
  const [tracks, setTracks] = useState<Track[] | null>(null)

  useEffect(() => {
    api.getDailyMix()
      .then((data) => {
        setTracks(data.tracks)
      })
      .catch(() => setTracks([]))
  }, [])

  return (
    <section className="view active">
      <div className="view-header">
        <button className="icon-btn" onClick={() => navigate(-1)}>
          <Icon name="chevron" size={20} className="back-chevron" />
        </button>
        <div>
          <h2>Ежедневный микс</h2>
          <span className="hint">Подборка на основе ваших предпочтений</span>
        </div>
      </div>
      <TrackList
        tracks={tracks}
        emptyMessage="Недостаточно данных для создания микса"
      />
    </section>
  )
}
