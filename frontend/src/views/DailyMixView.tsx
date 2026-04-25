import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { TrackList } from '@/components/TrackList/TrackList'
import { Icon } from '@/components/Icon/Icon'
import { api } from '@/lib/api'
import type { DailyPlaylistResponse } from '@/types/api'

export function DailyMixView() {
  const navigate = useNavigate()
  const [data, setData] = useState<DailyPlaylistResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    api.getDailyPlaylist()
      .then(setData)
      .catch(() =>
        setData({
          internal_tracks: [],
          external_tracks: [],
          global_top: [],
          generated_at: '',
          expires_at: '',
        })
      )
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const handleRefresh = useCallback(() => {
    setRefreshing(true)
    api.refreshDailyPlaylist()
      .then(() => load())
      .catch(() => load())
      .finally(() => setRefreshing(false))
  }, [load])

  const internalTracks = loading ? null : (data?.internal_tracks ?? [])
  const externalTracks = data?.external_tracks ?? []

  return (
    <section className="view active">
      <div className="view-header">
        <button className="icon-btn" onClick={() => navigate(-1)}>
          <Icon name="chevron" size={20} className="back-chevron" />
        </button>
        <div style={{ flex: 1 }}>
          <h2>Плейлист дня</h2>
          <span className="hint">Подборка на основе ваших предпочтений</span>
        </div>
        <button
          className="icon-btn"
          onClick={handleRefresh}
          disabled={refreshing || loading}
          aria-label="Обновить плейлист"
        >
          <Icon
            name="refresh"
            size={20}
            className={refreshing ? 'spin' : undefined}
          />
        </button>
      </div>

      <TrackList
        tracks={internalTracks}
        emptyMessage="Недостаточно данных для создания плейлиста"
      />

      {!loading && externalTracks.length > 0 && (
        <>
          <div className="section-header">
            <span className="section-title">Открытия</span>
          </div>
          <TrackList
            tracks={externalTracks}
            emptyMessage=""
          />
        </>
      )}
    </section>
  )
}
