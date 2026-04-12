import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon/Icon'
import { TrackList } from '@/components/TrackList/TrackList'
import type { Track } from '@/types/api'

interface Props {
  artistName: string
  onClose: () => void
}

export function ArtistView({
  artistName,
  onClose,
}: Props) {
  const [tracks, setTracks] = useState<
    Track[] | null
  >(null)

  useEffect(() => {
    api
      .getTracks({ q: artistName, size: 50 })
      .then((data) =>
        setTracks(
          data.items.filter(
            (t) =>
              t.artist
                ?.toLowerCase()
                .includes(
                  artistName.toLowerCase(),
                ),
          ),
        ),
      )
      .catch(() => setTracks([]))
  }, [artistName])

  return (
    <div className="author-view">
      <div className="author-view-header">
        <button
          className="author-back-btn icon-btn"
          onClick={onClose}
        >
          <Icon name="chevron" size={18} />
          Назад
        </button>
      </div>

      <div className="author-hero">
        <div className="author-avatar">
          <Icon name="music" size={40} />
        </div>
        <div className="author-name">
          {artistName}
        </div>
        <p
          className="author-username"
          style={{ marginTop: 8 }}
        >
          Исполнитель
        </p>
      </div>

      <div className="section-header">
        <span className="section-title">
          Треки на платформе
        </span>
      </div>

      <TrackList
        tracks={tracks}
        emptyMessage="Треков этого исполнителя пока нет"
      />
    </div>
  )
}
