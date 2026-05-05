import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { TrackList } from '@/components/TrackList/TrackList'
import { Icon } from '@/components/Icon/Icon'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import type { DailyPlaylistResponse } from '@/types/api'

export function DailyMixView() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const toast = useToast()
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

  const handleShare = useCallback(async () => {
    const url = `${window.location.origin}${import.meta.env.BASE_URL}daily-mix`
    try {
      if (navigator.share) {
        await navigator.share({
          title: t('dailyMix.title'),
          text: t('dailyMix.hint'),
          url,
        })
        return
      }
      await navigator.clipboard.writeText(url)
      toast.success('Ссылка скопирована')
    } catch {
      toast.error('Не удалось поделиться')
    }
  }, [t, toast])

  return (
    <section className="view active">
      <div className="view-header">
        <button className="icon-btn" onClick={() => navigate(-1)}>
          <Icon name="chevron" size={20} className="back-chevron" />
        </button>
        <div style={{ flex: 1 }}>
          <h2>{t('dailyMix.title')}</h2>
          <span className="hint">
            {t('dailyMix.hint')}
          </span>
        </div>
        <button
          className="icon-btn"
          onClick={() => {
            void handleShare()
          }}
          aria-label="Поделиться"
        >
          <Icon name="share" size={18} />
        </button>
        <button
          className="icon-btn"
          onClick={handleRefresh}
          disabled={refreshing || loading}
          aria-label={t('dailyMix.refreshAria')}
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
        emptyMessage={t('dailyMix.empty')}
      />

      {!loading && externalTracks.length > 0 && (
        <>
          <div className="section-header">
            <span className="section-title">
              {t('dailyMix.discoveries')}
            </span>
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
