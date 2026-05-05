import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { TrackList } from '@/components/TrackList/TrackList'
import { Icon } from '@/components/Icon/Icon'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import type { WeeklyPlaylistResponse } from '@/types/api'

export function WeeklyMixView() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const toast = useToast()
  const [data, setData] = useState<WeeklyPlaylistResponse | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    setLoading(true)
    api
      .getWeeklyPlaylist()
      .then(setData)
      .catch(() =>
        setData({
          internal_tracks: [],
          external_tracks: [],
          generated_at: '',
          expires_at: '',
        })
      )
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const internalTracks = loading
    ? null
    : (data?.internal_tracks ?? [])
  const externalTracks = data?.external_tracks ?? []

  const handleShare = useCallback(async () => {
    const url = `${window.location.origin}${import.meta.env.BASE_URL}weekly-mix`
    try {
      if (navigator.share) {
        await navigator.share({
          title: t('weeklyMix.title'),
          text: t('weeklyMix.hint'),
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
          <h2>{t('weeklyMix.title')}</h2>
          <span className="hint">
            {t('weeklyMix.hint')}
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
      </div>

      <TrackList
        tracks={internalTracks}
        emptyMessage={t('weeklyMix.empty')}
      />

      {!loading && externalTracks.length > 0 && (
        <>
          <div className="section-header">
            <span className="section-title">
              {t('weeklyMix.discoveries')}
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
