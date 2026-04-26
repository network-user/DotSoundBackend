import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { TrackList } from '@/components/TrackList/TrackList'
import { Icon } from '@/components/Icon/Icon'
import {
  usePlayerActions,
  usePlayerMeta,
} from '@/store/PlayerContext'
import { api } from '@/lib/api'
import type { Track } from '@/types/api'

export function RadioView() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { track: currentTrack } = usePlayerMeta()
  const { playTrack } = usePlayerActions()
  const [tracks, setTracks] = useState<Track[] | null>(null)
  const seedId = searchParams.get('seed') || currentTrack?.id?.toString()

  useEffect(() => {
    if (!seedId) return
    api.getRadio(Number(seedId), 20)
      .then((data) => setTracks(data.tracks))
      .catch(() => setTracks([]))
  }, [seedId])

  const handlePlayAll = () => {
    if (tracks && tracks.length > 0) {
      playTrack(tracks[0])
    }
  }

  return (
    <section className="view active">
      <div className="view-header">
        <button className="icon-btn" onClick={() => navigate(-1)}>
          <Icon name="chevron" size={20} className="back-chevron" />
        </button>
        <div>
          <h2>Радио</h2>
          <span className="hint">Бесконечная подборка похожих треков</span>
        </div>
      </div>
      {tracks && tracks.length > 0 && (
        <button className="radio-play-all" onClick={handlePlayAll}>
          <Icon name="play" size={16} />
          <span>Воспроизвести</span>
        </button>
      )}
      <TrackList
        tracks={tracks}
        emptyMessage="Недостаточно данных для радио"
      />
    </section>
  )
}
